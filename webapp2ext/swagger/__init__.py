"""Decorators to define and decorate an API

Note:

All the magic happen at import time; if the api was badly defined,
it could result in unhelpful import errors in your tests.

If you find strange import errors, start the shell and try to `import education`.
The first fresh import will tell you what went wrong.

usage:
    from webapp2ext import swagger

    # Create an Api instance
    api = swagger.Api(
        host="http://0.0.0.0:8080/", path='/api/v1/', version='1'
    )

    # define your schemas
    api.schema(
        "Student",
        description="Student schema",
        properties= {
            "lastName": String(required=True),
            "firstName": String(required=True),
            "studentId": String(required=True),
        }
    )

    # For each resource, create a resource object
    student_resource = api.resource(
        path="/students",
        desc="Resource about current student"
    )

    # Create controllers for a resource. It should be a subclass of
    # swagger.ApiRequestHandler and have a  `path` class attribute.
    class StudentListHandler(swagger.ApiRequestHandler):

        path = student_resource.endpoint('/students/<studentId>')

        # Document every methods (the ones matching to http methods)
        @path.operation(
            type_="Student",
            alias="getStudents",
            parameters=[
                swagger.String(
                    name="studentId",
                    description="Matricule of the student",
                    param_type="path"
                )
            ],
            responses=[
                swagger.Message(200, "Ok"),
                swagger.Message(401, "Unauthorized"),
                swagger.Message(403, "Forbidden"),
                swagger.Message(404, "Not Found"),
            ]
        )
        def get(self, studentId):
            "Fetch info for a student (used as title in swagger)"

    # Use the api routes to create a WSGI app
    # It will generate the route for all swagger.ApiRequestHandler
    # and register some routes for /api/v1/api-docs
    import webapp2

    app = webapp2.WSGIApplication(
        [
            api.routes(),

            # some extra non api related handlers
            ('/', 'controller.somewhere.MainHandler',)
        ]
    )

TODO: check swagger support of `allOf` json-schema properties and implemet
it either way (merging and duplicating definitions if necessary)

example usage:

http://spacetelescope.github.io/understanding-json-schema/reference/combining.html#allof

"""
import json
import operator
import re
import weakref
from collections import deque
from itertools import chain

import webapp2
from google.appengine.api import users
from jsonschema import Draft4Validator, RefResolver
from webapp2_extras import routes


_primitives = set(
    ["array", "boolean", "integer", "number", "null", "object", "string", "void"]
)


def camelCase(word):
    """Convert python variable names to camelCase names

    """
    parts = word.split('_')
    return parts[0] + ''.join(w.title() for w in parts[1:])


def to_dict(root, ctx=None):
    """convert a dict deep values or a swagger schema instance to
    a dict containing only primitive values.

    """
    if ctx is None:
        ctx = _Context()
    clone = root.to_dict(ctx) if hasattr(root, "to_dict") else root.copy()
    nodes = deque([clone])

    while nodes:
        node = nodes.pop()
        if hasattr(node, "iterkeys"):
            _walk_dict(ctx, node, nodes)
        elif isinstance(node, (list, tuple,)):
            _walk_list(ctx, node, nodes)

    return clone


def _walk_dict(ctx, node, nodes):
    for key in node.iterkeys():
        _to_dict(ctx, node, key, nodes)


def _walk_list(ctx, node, nodes):
    for i in range(len(node)):
        _to_dict(ctx, node, i, nodes)


def _to_dict(ctx, node, key, nodes):
    if hasattr(node[key], "to_dict"):
        node[key] = node[key].to_dict(ctx)
        nodes.append(node[key])
    elif hasattr(node[key], "copy"):
        node[key] = node[key].copy()
        nodes.append(node[key])
    elif isinstance(node[key], (list, tuple,)):
        node[key] = list(node[key])
        nodes.append(node[key])


class _Type(object):
    """Countainer for a json-schema (or swagger paramter) object.

    """

    def __init__(
        self,
        name=None,
        type_=None,
        description=None,
        format=None,
        required=None,
        default=None,
        param_type=None,
        enum=None
    ):
        self.name = name
        self.type = type_
        self.description = description
        self.format = format
        self.required = required
        self.default = default
        self.enum = enum
        self.param_type = param_type

    def to_dict(self, ctx):
        return dict(
            (camelCase(k), v,)
                for (k, v,) in self.__dict__.iteritems()
                if v is not None
        )


class Object(_Type):
    """Json-schema Object type. Rarelly used directly. Use Api.Schema()
    or Api.ref() or Param() instead.

    The schema id should just be a name. You shouldn't prefix it with
    `#`.

    """
    def __init__(
        self,
        id=None,
        properties=None,
        required=(),
        pattern_properties=None,
        additional_properties=None,
        **kw
    ):
        super(Object, self).__init__(type_="object", required=required, **kw)

        if properties is None:
            properties = {}
            additional_properties = True
        for name in required:
            if name not in properties:
                raise ValueError(
                    "%s cannot be required since it's not a property"
                )
        self.id = id
        self.properties = properties
        self.required = required if required else None
        self.pattern_properties = pattern_properties
        self.additional_properties = additional_properties


class Param(_Type):
    """Generic Parameter to use as element of a operation parameter
    array to define a complex type parameter
    (e.g. other than integer or string).

    """
    def __init__(self, type_, **kw):
        super(Param, self).__init__(type_=type_, **kw)


class Array(_Type):
    """Json-schema array type.

    """
    def __init__(self, items, unique_items=None, **kw):
        super(Array, self).__init__(type_="array", **kw)
        self.items = items
        self.unique_items = unique_items


class String(_Type):
    """Json-schema string type

    """
    def __init__(self, **kw):
        super(String, self).__init__(type_="string", **kw)


class _Number(_Type):
    """Json-schema base type for Float and Int

    """
    def __init__(
        self,
        minimum=None,
        maximum=None,
        exclusive_minimum=None,
        exclusive_maximum=None,
        **kw
    ):
        super(_Number, self).__init__(type_="number", **kw)

        self.minimum = minimum
        self.maximum = maximum
        self.exclusive_minimum = exclusive_minimum
        self.exclusive_maximum = exclusive_maximum


class Int(_Number):
    """Json-schema integer type

    """
    def __init__(self, long_=False, **kw):
        super(Int, self).__init__(**kw)

        self.type = "integer"

        if long_:
            self.format = "long"
        else:
            self.format = None


class Float(_Number):
    """Json-schema Float type

    """
    def __init__(self, double=False, multiple_of=None, **kw):
        super(Float, self).__init__(**kw)

        if double:
            self.format = "double"
        self.multiple_of = multiple_of


class Boolean(_Type):
    """Json-schema integer type

    """
    def __init__(self, **kw):
        super(Boolean, self).__init__(type_="boolean", **kw)


class _Ref(object):
    """Json-schema type referencing a complex type
    (defined by Api.schema)

    It supports both json pointer and swagger simple referencing.

    It will use json pointer by default. Pass a context object to
    `to_dict` with an output set to `education.swagger.SWAGGER_DOC`
    to use swagger doc referencing.

    """
    def __init__(self, name, required=False):
        self.name = name
        self.required = required

    def to_dict(self, ctx):
        result = {}
        if ctx.output == SWAGGER_DOC:
            result["$ref"] = self.name
        else:
            result["$ref"] = "%s#/%s" %(ctx.api.schema_path, self.name,)
        return result


class Message(object):
    """Message object. Used to define the http status code an operation
    might respond with

    """

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def to_dict(self, ctx):
        return {
            "code": self.code,
            "message": self.message
        }


JSON_SCHEMA = "json-schema"
SWAGGER_DOC = "api-doc"


class _Context(object):

    def __init__(self, api=None, output=JSON_SCHEMA):
        if api is not None:
            self.api = weakref.proxy(api)
        else:
            self.api = None
        self.output = output


class Api(object):
    """Decorator (decorator builder) for webapp2 request handler.

    Generate routes, schemas and the swagger api doc of an api.

    """

    # api doc `swaggerVersion` attribute
    swagger_version = '1.2'

    def __init__(self, host, path, version):
        """Api constructor.

        `host`: used for the schema URI.
        `path`: used a prefix for the route.
        `version`: used for the api doc `apiVersion` attribute


        """
        if path[0] != '/':
            raise ValueError('path cannot be relative')
        self.host = host.rstrip('/')
        self.path = path.rstrip('/')
        self.version = version
        self.resources = {}
        self._schemas = {}
        self._resolver = RefResolver(self.schema_path, {}, store={})

    @property
    def base_path(self):
        return ''.join([self.host, self.path])

    @property
    def schema_path(self):
        return "%s/json-schemas" % self.base_path

    def api_doc(self):
        """Generate the api doc (as a dict).

        It generate a route documentation listing all the resources.

        """
        return {
            "apiVersion": self.version,
            "swaggerVersion": self.swagger_version,
            "apis": sorted(
                [r.summary() for r in self.resources.values()],
                key=operator.itemgetter('path')
            ),
        }

    def _json_handler(self, data, status=200):
        resp = webapp2.Response(
            json.dumps(data, sort_keys=True, indent=4)
        )
        resp.headers['Content-Type'] = "application/json"
        resp.status = status
        return resp

    def schema_handler(self, request):
        """http handler for the schema request.

        """
        return self._json_handler(self.schemas())

    def api_doc_handler(self, request):
        """http handler for the route api-doc request.

        """
        return self._json_handler(self.api_doc())

    def apis_handler(self, request, path):
        """http handler for a resource api-doc request.

        """
        resource = self.resources.get('/%s' % path, None)
        if resource is None:
            return self._json_handler({'error': 'resource not found'}, 404)

        return self._json_handler(resource.api_doc())

    def routes(self):
        """Return a route collection for an api
        (including the api-doc and schema):

        - the request handler routes are define by the
          `swagger.ApiRequestHandler.path` class attributes.
        - the api-doc path `<api.path>/api-docs`
        - the schema path `<api.path>/json-schemas/`

        """
        rel_routes = []
        rel_routes.append(
            webapp2.Route('/api-docs', self.api_doc_handler, methods=['GET'])
        )
        rel_routes.append(
            webapp2.Route(
                '/api-docs/<path:.+>', self.apis_handler, methods=['GET']
            )
        )
        rel_routes.append(
            webapp2.Route(
                '/json-schemas', self.schema_handler, methods=['GET']
            )
        )

        for resource in self.resources.itervalues():
            for api in resource.apis.itervalues():
                rel_routes.append(webapp2.Route(api.path, api.handler,))
        return routes.PathPrefixRoute(self.path, rel_routes)

    def resource(self, path, desc=None):
        """Define a new resource.

        """
        if path not in self.resources:
            self.resources[path] = _Resource(self, path, desc)
        return self.resources[path]

    def schema(self, name, properties=None, additional_properties=False, **kw):
        """Create a new schema definition.

        The base schema can currently only be defined as objects
        (swagger only define models as object).

        """
        properties = {} if properties is None else properties
        kw.setdefault('required', [])

        for prop_name, prop in properties.iteritems():
            if prop.required:
                kw['required'].append(prop_name)
            prop.required = None

        definition = Object(
            id=name,
            properties=properties,
            additional_properties=additional_properties,
            **kw
        )
        self._schemas[name] = definition
        self._update_resolver()

    def schemas(self):
        """Json-schema for all complex type defined in an API.

        """
        schemas = {
            "id": "%s#" % self.schema_path,
            "$schema": "http://json-schema.org/draft-04/schema#",
        }
        for s_id, s in self._schemas.iteritems():
            if s is None:
                continue
            schemas[s_id] = s
        return to_dict(schemas, ctx=_Context(self))

    def ref(self, name, required=False):
        """Return an object with "$ref" attribute.

        Suitable to be used in json schema document. Use Api.model if
        the reference is to be used in swagger api document.

        """
        self._schemas.setdefault(name, None)
        return _Ref(name, required=required)

    def _update_resolver(self):
        self._resolver.store[self.schema_path] = self.schemas()

    def validate(self, schema, data):
        """Create json-schema validator for a complex type.

        """
        with self._resolver.resolving('#/%s' % schema) as schema:
            validator = Draft4Validator(schema, resolver=self._resolver)
            validator.validate(data)


class _Resource(object):
    """An api resource.

    The path parameter defines the relative of the resource api-doc
    (relative to `/api-doc`). It should match the root path
    of a resource it doesn't need to.

    """
    def __init__(self, api, path, desc):
        self.api = weakref.proxy(api)
        self.path = path
        self.description = desc
        self.apis = {}
        self.models = set()

    def add_model(self, type_):
        """Add a model to the resource api documentation.

        It will walk the model to find nested complex type requirement.

        """
        if type_ in _primitives:
            return
        if type_ in self.models:
            return
        if type_ not in self.api._schemas:
            raise ValueError("No schema with that id (%s)." % type_)

        skip = set(self.models)
        to_check = deque([type_])

        while len(to_check) > 0:
            name = to_check.pop()
            to_check.extend(self._check_type(name, skip))
            skip.add(name)
            self.models.add(name)

    def _check_type(self, type_, skip):
        if type_ in skip:
            return ()

        schema = self.api._schemas[type_]
        if schema is None:
            return ()

        schemas_to_check = []

        pp = schema.pattern_properties or {}
        for prop in chain(schema.properties.itervalues(), pp.itervalues()):
            if isinstance(prop, _Ref):
                schemas_to_check.append(prop.name)
                continue

            if not isinstance(prop, Array):
                continue

            if isinstance(prop.items, _Ref):
                schemas_to_check.append(prop.items.name)
                continue
        return schemas_to_check

    def summary(self):
        """Api doc summary for that resource
        (used for the root api doc).

        """
        return {
            'path': self.path,
            'description': self.description,
        }

    def endpoint(self, path):
        """Add an api URL for that resource.

        """
        if path not in self.apis:
            self.apis[path] = _EndPoint(self, path)
        return self.apis[path]

    def api_doc(self):
        """Return the the api-doc of that resource (as a dict)

        """
        models = {}
        for name in self.models:
            schema = self.api._schemas[name]
            if schema is None:
                continue
            models[name] = schema

        return to_dict(
            {
                "apiVersion": str(self.api.version),
                "swaggerVersion": self.api.swagger_version,
                "basePath": self.api.base_path,
                "resourcePath": self.path,
                "apis": self.apis.values(),
                "models": models
            },
            ctx=_Context(self, SWAGGER_DOC)
        )


class _EndPoint(object):
    """An Api URL and a collection of operation associated to that URL.

    The path should be defined as a webapp2.Route URL pattern
    (with `<` and `>` to delimite path variables).

    """
    param_pattern = re.compile(r"<([^>:]+)(:[^>]+)?>")

    def __init__(self, resource, path):
        self.resource = weakref.proxy(resource)
        self.path = path
        self.swagger_path = self.param_pattern.sub(r"{\1}", path)
        self.operations = []
        self.handler = None

    def bind(self, handler):
        """Bind a request handler to an endpoint.

        """
        self.handler = handler

    def operation(self, type_, alias, items=None, parameters=(), responses=()):
        """Decoration to define metadata about an operation.

        It will use the method name to know the operation http method
        and method doc to define a summary.

        TODO: use the remaining method documentation to define the
        operation description attribute.

        """
        if items:
            self.resource.add_model(items.name)
        else:
            self.resource.add_model(type_)

        for param in parameters:
            if isinstance(param, Param):
                self.resource.add_model(param.type)

        def deco(meth):
            self.operations.append(
                Operation(
                    method=meth.__name__.upper(),
                    summary=meth.__doc__.strip().splitlines()[0],
                    type_=type_,
                    items=items,
                    alias=alias,
                    parameters=parameters,
                    responses=responses
                )
            )
            return meth
        return deco

    def to_dict(self, ctx):
        return {
            "path": self.swagger_path,
            "operations": self.operations
        }


class Operation(object):
    """Document a request handler.

    - the `type_` argument should the name of a model.
    - the `parameters` argument should be list of `Param` or `_Type`
      instances.
    - the `responses` argument should the a list `Message` the operation
      might answer with.

    """

    def __init__(
        self, method, summary, type_, alias, items=None, parameters=(), responses=()
    ):
        self.method = method
        self.summary = summary
        self.type = type_
        self.items = items
        self.alias = alias
        self.parameters = parameters
        self.responses = responses

    def to_dict(self, ctx):
        result = {
            "method": self.method,
            "summary": self.summary,
            "type": self.type,
            "nickname": self.alias,
            "parameters": self.parameters,
            "responseMessages": self.responses,
        }
        if self.items:
            result["items"] = self.items
        return result


class MetaRequestHandler(type):
    """Metaclass use to bind a request handler to a endpoint and a
    route.

    Require the class to have a `path` class attribute.

    """

    def __init__(cls, name, bases, dct):
        super(MetaRequestHandler, cls).__init__(name, bases, dct)
        if 'path' not in dct:
            return
        if hasattr(dct['path'], "__iter__"):
            for path in dct['path']:
                path.bind(cls)
        else:
            dct['path'].bind(cls)


class ApiRequestHandler(webapp2.RequestHandler):
    """Base Request Handler for json API Request.

    Must define a `path` class attribute.

    """
    __metaclass__ = MetaRequestHandler

    def render_json(self, data, status_code=200):
        self.response.status = status_code
        self.response.headers['Content-Type'] = "application/json"
        self.response.write(json.dumps(data))

    @staticmethod
    def get_current_user():
        return users.get_current_user()

    @classmethod
    def get_current_user_id(cls):
        user = cls.get_current_user()
        if user:
            return int(user.user_id() or 0)

    def login_required(self, msg=None):
        user = self.get_current_user()
        if not user:
            self.abort(401, msg)
        else:
            return user

    def admin_required(self, msg=None, admin_msg=None):
        user = self.login_required(msg=msg)
        if not users.is_current_user_admin():
            self.abort(403, admin_msg)
        return user

    def handle_exception(self, e, debug):
        if (
            isinstance(e, webapp2.HTTPException)
            and e.code >= 400
            and e.code < 500
        ):
            self.render_json({"error": str(e)}, e.code)
        else:
            super(ApiRequestHandler, self).handle_exception(e, debug)

