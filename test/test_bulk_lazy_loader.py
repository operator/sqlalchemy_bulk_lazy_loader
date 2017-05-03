from sqlalchemy.orm import attributes, create_session
from sqlalchemy import event
from sqlalchemy.engine import Engine
from test import _fixtures

class TestBulkLazyLoader(_fixtures.FixtureTest):

    def count_query(self, conn, cursor, statement, parameters, context, executemany):
        self.num_queries += 1

    def setup(self):
        super().setup()
        self.num_queries = 0
        event.listen(Engine, 'before_cursor_execute', self.count_query)

    def teardown(self):
        super().teardown()
        event.remove(Engine, 'before_cursor_execute', self.count_query)

    def test_load_one_to_one(self):
        User = self.classes.User
        UserInfo = self.classes.UserInfo
        session = create_session()

        users = session.query(User).order_by(self.tables.users.c.id.asc()).all()
        self.num_queries = 0

        # make sure no relations are loaded
        for user in users:
            model_dict = attributes.instance_dict(user)
            assert 'user_info' not in model_dict

        # trigger a lazy load on the first user
        users[0].user_info

        # only 1 query should have been generated to load all the child relationships
        assert self.num_queries == 1
        self.num_queries = 0

        user1_dict = attributes.instance_dict(users[0])
        user2_dict = attributes.instance_dict(users[1])
        user3_dict = attributes.instance_dict(users[2])
        user4_dict = attributes.instance_dict(users[3])

        assert UserInfo(id=1, details='is cool', user_id=7) == user1_dict['user_info']
        assert UserInfo(id=2, details='is not cool', user_id=8) == user2_dict['user_info']
        assert None == user3_dict['user_info']
        assert UserInfo(id=3, details='is moderately cool', user_id=10) == user4_dict['user_info']

        # backrefs should also not trigger loading
        assert users[0].user_info.user == users[0]
        assert users[1].user_info.user == users[1]
        assert users[3].user_info.user == users[3]

        # no new queries should have been generated
        assert self.num_queries == 0


    def test_load_one_to_many(self):
        User = self.classes.User
        Address = self.classes.Address
        session = create_session()

        users = session.query(User).order_by(self.tables.users.c.id.asc()).all()
        self.num_queries = 0

        # make sure no relations are loaded
        for user in users:
            model_dict = attributes.instance_dict(user)
            assert 'addresses' not in model_dict

        # trigger a lazy load on the first user
        users[0].addresses

        # only 1 query should have been generated to load all the child relationships
        assert self.num_queries == 1
        self.num_queries = 0

        user1_dict = attributes.instance_dict(users[0])
        user2_dict = attributes.instance_dict(users[1])
        user3_dict = attributes.instance_dict(users[2])
        user4_dict = attributes.instance_dict(users[3])

        assert [
            Address(id=1, email_address='jack@bean.com', user_id=7),
        ] == user1_dict['addresses']
        assert [
            Address(id=2, email_address='jackjr@wood.com', user_id=8),
            Address(id=3, email_address='jackjr@bettyboop.com', user_id=8),
            Address(id=4, email_address='jackjr@lala.com', user_id=8),
        ] == user2_dict['addresses']
        assert [
            Address(id=5, email_address='fred@fred.com', user_id=9),
        ] == user3_dict['addresses']
        assert [] == user4_dict['addresses']

        # backrefs should also not trigger loading
        for address in users[0].addresses:
            assert address.user == users[0]
        for address in users[1].addresses:
            assert address.user == users[1]
        for address in users[2].addresses:
            assert address.user == users[2]

        # no new queries should have been generated
        assert self.num_queries == 0

    def test_load_many_to_one(self):
        User = self.classes.User
        Address = self.classes.Address
        session = create_session()

        addresses = session.query(Address).order_by(self.tables.addresses.c.id.asc()).all()
        self.num_queries = 0

        # make sure no relations are loaded
        for address in addresses:
            model_dict = attributes.instance_dict(address)
            assert 'user' not in model_dict

        # trigger a lazy load on the first user
        addresses[0].user

        # only 1 query should have been generated to load all the child relationships
        assert self.num_queries == 1
        self.num_queries = 0

        address1_dict = attributes.instance_dict(addresses[0])
        address2_dict = attributes.instance_dict(addresses[1])
        address3_dict = attributes.instance_dict(addresses[2])
        address4_dict = attributes.instance_dict(addresses[3])
        address5_dict = attributes.instance_dict(addresses[4])

        assert User(id=7, name='jack', parent_id=None) == address1_dict['user']
        assert User(id=8, name='jack jr', parent_id=7) == address2_dict['user']
        assert User(id=8, name='jack jr', parent_id=7) == address3_dict['user']
        assert User(id=8, name='jack jr', parent_id=7) == address4_dict['user']
        assert User(id=9, name='fred', parent_id=7) == address5_dict['user']

        # no new queries should have been generated
        assert self.num_queries == 0

    def test_load_one_to_many_self_refencing(self):
        User = self.classes.User
        session = create_session()

        users = (
            session.query(User)
                .filter(self.tables.users.c.id.in_([7,8]))
                .order_by(self.tables.users.c.id.asc())
                .all()
        )
        self.num_queries = 0

        # make sure no relations are loaded
        for user in users:
            model_dict = attributes.instance_dict(user)
            assert 'children' not in model_dict

        # trigger a lazy load on the first user
        users[0].children

        # only 1 query should have been generated to load all the child relationships
        assert self.num_queries == 1
        self.num_queries = 0

        user1_dict = attributes.instance_dict(users[0])
        user2_dict = attributes.instance_dict(users[1])

        assert [
            User(id=8, name='jack jr', parent_id=7),
            User(id=9, name='fred', parent_id=7),
        ] == user1_dict['children']
        assert [
            User(id=10, name='jack jr jr', parent_id=8),
        ] == user2_dict['children']

        # backrefs should also not trigger loading
        for child in users[0].children:
            assert child.parent == users[0]
        for child in users[1].children:
            assert child.parent == users[1]

        # no new queries should have been generated
        assert self.num_queries == 0


    def test_load_many_to_one_self_refencing(self):
        User = self.classes.User
        session = create_session()

        users = (
            session.query(User)
                .filter(self.tables.users.c.id.in_([8, 9, 10]))
                .order_by(self.tables.users.c.id.asc())
                .all()
        )
        self.num_queries = 0

        # make sure no relations are loaded
        for user in users:
            model_dict = attributes.instance_dict(user)
            assert 'parent' not in model_dict

        # trigger a lazy load on the first user
        users[0].parent

        # only 1 query should have been generated to load all the child relationships
        assert self.num_queries == 1
        self.num_queries = 0

        user1_dict = attributes.instance_dict(users[0])
        user2_dict = attributes.instance_dict(users[1])
        user3_dict = attributes.instance_dict(users[2])

        assert User(id=7, name='jack', parent_id=None) == user1_dict['parent']
        assert User(id=7, name='jack', parent_id=None) == user2_dict['parent']
        assert User(id=8, name='jack jr', parent_id=7) == user3_dict['parent']

        # no new queries should have been generated
        assert self.num_queries == 0

    def test_load_many_to_many(self):
        User = self.classes.User
        Thing = self.classes.Thing
        session = create_session()

        users = session.query(User).order_by(self.tables.users.c.id.asc()).all()
        self.num_queries = 0

        # make sure no relations are loaded
        for user in users:
            model_dict = attributes.instance_dict(user)
            assert 'things' not in model_dict

        # trigger a lazy load on the first user
        users[0].things

        # only 1 query should have been generated to load all the child relationships
        assert self.num_queries == 1
        self.num_queries = 0

        user1_dict = attributes.instance_dict(users[0])
        user2_dict = attributes.instance_dict(users[1])
        user3_dict = attributes.instance_dict(users[2])
        user4_dict = attributes.instance_dict(users[3])

        assert [
            Thing(id=1, name='dog'),
        ] == user1_dict['things']
        assert [
            Thing(id=1, name='dog'),
        ] == user2_dict['things']
        assert [
            Thing(id=2, name='lamp'),
        ] == user3_dict['things']
        assert [
            Thing(id=2, name='lamp'),
            Thing(id=3, name='chair'),
        ] == user4_dict['things']

        # no new queries should have been generated
        assert self.num_queries == 0








