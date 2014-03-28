from jsonschema import ValidationError

from webapp2ext import swagger
from webapp2ext.swagger import Api, String, Int, Array, Message, Param
from webapp2ext.swagger.tests.utils import TestCase


class Handler(object):
    """Some resource

    """

    def get(self):
        """List resource

        """

    def post(self):
        """Add resource"""


class TestSwagger(TestCase):

    def test_define_ressources(self):
        api = Api(
            host="http://example.com/",
            path='/api/v1/',
            version='1'
        )
        self.assertEqual('http://example.com', api.host)
        self.assertEqual('/api/v1', api.path)
        self.assertEqual(
            'http://example.com/api/v1',
            api.base_path
        )
        self.assertEqual('1', api.version)
        self.assertEqual({
                "apiVersion": "1",
                "swaggerVersion": "1.2",
                "apis": []
            },
            api.api_doc()
        )

        api.resource(path="/res", desc="Some resource")
        self.assertEqual({
                "apiVersion": "1",
                "swaggerVersion": "1.2",
                "apis": [
                    {
                        "path": "/res",
                        "description": "Some resource"
                    }
                ]
            },
            api.api_doc()
        )

    def test_schema(self):
        api = Api(
            host="http://example.com/",
            path='/api/v1/',
            version='1'
        )
        api.schema(
            'User',
            properties={
                "name": String(required=True),
                "logoutUrl": String(),
            },
        )
        schema = api.schemas()
        self.assertEqual(
            "http://example.com/api/v1/json-schemas#",
            schema['id']
        )
        self.assertEqual(
            "http://json-schema.org/draft-04/schema#",
            schema['$schema']
        )
        self.assertEqual(
            {
                "id": "User",
                "type": "object",
                'additionalProperties': False,
                "properties": {
                    "name": {"type": "string"},
                    "logoutUrl": {"type": "string"}
                },
                "required": ["name"]
            },
            schema['User']
        )

    def test_schema_with_ref(self):
        api = Api(
            host="http://example.com/",
            path='/api/v1/',
            version='1'
        )
        api.schema(
            'Student',
            properties={
                "name": String(required=True),
                "id": Int(required=True)
            },
        )
        api.schema(
            'StudentList',
            properties={
                "students": Array(items=api.ref('Student'), required=True)
            },
        )

        schema = api.schemas()


        self.assertEqual(
            "http://example.com/api/v1/json-schemas#",
            schema['id']
        )
        self.assertEqual(
            "http://json-schema.org/draft-04/schema#",
            schema['$schema']
        )
        self.assertEqual(
            {
                "id": "Student",
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "id": {"type": "integer"}
                },
                "required": ["name", "id"],
                'additionalProperties': False
            },
            schema['Student']
        )
        self.assertEqual({
                "students": {
                    "type": "array",
                    "items" : {
                        "$ref":
                            "http://example.com/api/v1/json-schemas#/Student"
                    }
                },
            },
            schema['StudentList']['properties']
        )

    def test_define_operation(self):
        self.maxDiff = None
        api = Api(
            host="http://example.com/",
            path='/api/v1/',
            version='1'
        )
        api.schema(
            'Student',
            properties={
                "name": String(required=True),
                "id": Int(required=True)
            },
        )
        api.schema(
            'StudentList',
            properties={
                'students': Array(api.ref('Student'), required=True),
            }
        )
        students = api.resource(path="/students", desc="Operations about students")
        path = students.endpoint(r"/students/")
        path.operation(
            type_="StudentList",
            alias="getStudends",
            responses=[
                Message(200, "Ok"),
                Message(401, "Unauthorized"),
                Message(403, "Forbidden"),
            ]
        )(Handler.get)
        path.operation(
            type_="Student",
            alias="addStudend",
            parameters=[
                Param(
                    name="body",
                    description="Student to add",
                    type_="Student",
                    param_type="body",
                    required=True
                )
            ],
            responses=[
                Message(200, "Ok"),
                Message(400, "Invalid student"),
                Message(401, "Unauthorized"),
                Message(403, "Forbidden"),
            ]
        )(Handler.post)


        path = students.endpoint(r"/students/<studenId:\d+>")
        path.operation(
            type_="Student",
            alias="getStudendById",
            parameters=[
                Int(
                    name="studenId",
                    description="student id",
                    required=True,
                    param_type="path",
                    minimum=1
                )
            ],
            responses=[
                Message(200, "Ok"),
                Message(401, "Unauthorized"),
                Message(403, "Forbidden"),
                Message(404, "Not Found"),
            ]
        )(Handler.get) # should be a different method, but it

        self.assertIn(r"/students/<studenId:\d+>", students.apis)
        self.assertEqual(
            {
                u"apiVersion": u"1",
                u"swaggerVersion": u"1.2",
                u"basePath": u"http://example.com/api/v1",
                u"resourcePath": u"/students",
                u"apis": [
                    {
                        u"path": u"/students/",
                        u"operations": [
                            {
                                u"method": u"GET",
                                u"summary": u"List resource",
                                u"type": u"StudentList",
                                u"nickname": u"getStudends",
                                u"parameters": [],
                                u"responseMessages": [
                                    {
                                        u"code": 200,
                                        u"message": u"Ok"
                                    },
                                    {
                                        u"code": 401,
                                        u"message": u"Unauthorized"
                                    },
                                    {
                                        u"code": 403,
                                        u"message": u"Forbidden"
                                    },
                                ]

                            },
                            {
                                u"method": u"POST",
                                u"summary": u"Add resource",
                                u"type": u"Student",
                                u"nickname": u"addStudend",
                                u"parameters": [
                                    {
                                        "name": "body",
                                        "description": "Student to add",
                                        "required": True,
                                        "type": "Student",
                                        "paramType": "body"
                                    }
                                ],
                                u"responseMessages": [
                                    {
                                        u"code": 200,
                                        u"message": u"Ok"
                                    },
                                    {
                                        u"code": 400,
                                        u"message": u"Invalid student"
                                    },
                                    {
                                        u"code": 401,
                                        u"message": u"Unauthorized"
                                    },
                                    {
                                        u"code": 403,
                                        u"message": u"Forbidden"
                                    },
                                ]

                            }
                        ],
                    },
                    {
                        u"path": u"/students/{studenId}",
                        u"operations": [
                            {
                                u"method": u"GET",
                                u"summary": u"List resource",
                                u"type": u"Student",
                                u"nickname": u"getStudendById",
                                u"parameters": [
                                    {
                                        u"name": u"studenId",
                                        u"description": u"student id",
                                        u"required": True,
                                        u"type": u"integer",
                                        u"paramType": u"path",
                                        u"minimum": 1
                                    }
                                ],
                                u"responseMessages": [
                                    {
                                        u"code": 200,
                                        u"message": u"Ok"
                                    },
                                    {
                                        u"code": 401,
                                        u"message": u"Unauthorized"
                                    },
                                    {
                                        u"code": 403,
                                        u"message": u"Forbidden"
                                    },
                                    {
                                        u"code": 404,
                                        u"message": u"Not Found"
                                    },
                                ]
                            }
                        ]
                    },
                ],
                u"models": {
                    u"Student": {
                        u"id": u"Student",
                        u"type": u"object",
                        u'additionalProperties': False,
                        u"properties": {
                            u"id": {
                                u"type": u"integer"
                            },
                            u"name": {
                                u"type": u"string"
                            }
                        },
                        u"required": [u"name", u"id"]
                    },
                    u"StudentList": {
                        u"id": u"StudentList",
                        u"type": u"object",
                        u'additionalProperties': False,
                        u"properties": {
                            u"students": {
                                u"type": "array",
                                u"items": {
                                    u"$ref": u"Student"
                                }
                            },
                        },
                        u"required": [u"students"]
                    }

                }
            },
            students.api_doc()
        )

    def test_define_operation_models(self):
        self.maxDiff = None
        api = Api(
            host="http://example.com/",
            path='/api/v1/',
            version='1'
        )
        api.schema(
            'Student',
            properties={
                "name": String(required=True),
                "id": Int(required=True)
            },
        )
        api.schema(
            'StudentList',
            properties={
                'students': Array(api.ref('Student'), required=True),
            }
        )
        students = api.resource(
            path="/students", desc="Operations about students"
        )
        path = students.endpoint(r"/students/")
        path.operation(
            type_="StudentList",
            alias="getStudends",
            responses=[
                Message(200, "Ok"),
                Message(401, "Unauthorized"),
                Message(403, "Forbidden"),
            ]
        )(Handler.get)

        self.assertEqual(
            {
                u"apiVersion": u"1",
                u"swaggerVersion": u"1.2",
                u"basePath": u"http://example.com/api/v1",
                u"resourcePath": u"/students",
                u"apis": [
                    {
                        u"path": u"/students/",
                        u"operations": [
                            {
                                u"method": u"GET",
                                u"summary": u"List resource",
                                u"type": u"StudentList",
                                u"nickname": u"getStudends",
                                u"parameters": [],
                                u"responseMessages": [
                                    {
                                        u"code": 200,
                                        u"message": u"Ok"
                                    },
                                    {
                                        u"code": 401,
                                        u"message": u"Unauthorized"
                                    },
                                    {
                                        u"code": 403,
                                        u"message": u"Forbidden"
                                    },
                                ]

                            }
                        ],
                    },
                ],
                u"models": {
                    u"Student": {
                        u"id": u"Student",
                        u"type": u"object",
                        u'additionalProperties': False,
                        u"properties": {
                            u"id": {
                                u"type": u"integer"
                            },
                            u"name": {
                                u"type": u"string"
                            }
                        },
                        u"required": [u"name", u"id"]
                    },
                    u"StudentList": {
                        u"id": u"StudentList",
                        u"type": u"object",
                        u'additionalProperties': False,
                        u"properties": {
                            u"students": {
                                u"type": "array",
                                u"items": {
                                    u"$ref": u"Student"
                                }
                            },
                        },
                        u"required": [u"students"]
                    }

                }
            },
            students.api_doc()
        )

    def test_define_routes(self):
        self.maxDiff = None
        api = Api(
            host="http://example.com/",
            path='/api/v1/',
            version='1'
        )
        api.schema(
            'Student',
            properties={
                "name": String(required=True),
                "id": Int(required=True)
            },
        )
        api.schema(
            'StudentList',
            properties={
                'students': Array(api.ref('Student'), required=True),
            }
        )
        students = api.resource(
            path="/students", desc="Operations about students"
        )
        path = students.endpoint(r"/students/")
        path.operation(
            type_="StudentList",
            alias="getStudends",
            responses=[
                Message(200, "Ok"),
                Message(401, "Unauthorized"),
                Message(403, "Forbidden"),
            ]
        )(Handler.get)
        path.bind(Handler)

        routes = api.routes()
        self.assertEqual('/api/v1', routes.prefix)
        self.assertEqual(
            [
                ("/api/v1/api-docs", api.api_doc_handler,),
                ("/api/v1/api-docs/<path:.+>", api.apis_handler,),
                ("/api/v1/json-schemas", api.schema_handler,),
                ("/api/v1/students/", Handler),
            ],
            [(r.template, r.handler) for r in routes.routes]
        )


class TestApi(TestCase):

    def test_validator(self):
        self.maxDiff = None
        api = Api(
            host="http://example.com/",
            path='/api/v1/',
            version='1'
        )
        api.schema(
            'Student',
            properties={
                "name": String(required=True),
                "id": Int(required=True)
            },
        )
        api.schema(
            'StudentList',
            properties={
                'students': Array(api.ref('Student'), required=True),
            }
        )

        self.assertRaises(ValidationError, api.validate, 'Student', {})

        try:
            api.validate(
                'Student',
                {
                    "name": "alice",
                    "id": 1
                }
            )
        except ValidationError:
            self.fail("Validation was suppose to pass. It failed instead")

class TestType(TestCase):

    def test_empty_type(self):
        self.assertEqual({}, swagger._Type().to_dict({}))


class TestObject(TestCase):

    def test_simple_object(self):
        o = swagger.Object()
        self.assertEqual(
            {
                "type": "object",
                "additionalProperties": True,
                "properties": {}
            },
            o.to_dict({})
        )

    def test_missing_required(self):
        self.assertRaises(ValueError, swagger.Object, required=["foo"])


class TestToDict(TestCase):

    def test_walk_primitives(self):
        self.assertEqual(
            {"a": 1, "b": "2", "c": {}},
            swagger.to_dict({"a": 1, "b": "2", "c": {}})
        )

    def test_walk_schema(self):
        subject = swagger.Object(properties={"a": Int()})
        self.assertEqual(
            {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "integer"
                    }
                }
            },
            swagger.to_dict(subject)
        )
        self.assertTrue(isinstance(subject, swagger.Object))
        self.assertTrue(isinstance(subject.properties["a"], Int))

    def test_walk_array(self):
        subject = {'list': [Int()]}
        self.assertEqual(
            {'list': [{"type": "integer"}]},
            swagger.to_dict(subject)
        )
        self.assertTrue(isinstance(subject['list'][0], Int))
