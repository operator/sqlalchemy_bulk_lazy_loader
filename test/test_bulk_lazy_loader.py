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

        # no new queries should have been generated
        assert self.num_queries == 0







