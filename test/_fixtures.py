from sqlalchemy import ForeignKey, Integer, String, Text, desc
from sqlalchemy.orm import backref, configure_mappers, mapper, relationship
from sqlalchemy.testing import fixtures
from sqlalchemy.testing.schema import Column, Table

__all__ = ()


class FixtureTest(fixtures.MappedTest):
    """A MappedTest pre-configured with a common set of fixtures."""

    run_define_tables = "once"
    run_setup_classes = "once"
    run_setup_mappers = "each"
    run_inserts = "each"
    run_deletes = "each"

    @classmethod
    def setup_classes(cls):
        class Base(cls.Comparable):
            pass

        class User(Base):
            pass

        class UserInfo(Base):
            pass

        class Address(Base):
            pass

        class Thing(Base):
            pass

    @classmethod
    def setup_mappers(cls):
        User, users = cls.classes.User, cls.tables.users
        UserInfo, user_infos = cls.classes.UserInfo, cls.tables.user_infos
        Address, addresses = cls.classes.Address, cls.tables.addresses
        Thing, things = cls.classes.Thing, cls.tables.things

        mapper(
            User,
            users,
            properties={
                "addresses": relationship(
                    Address,
                    backref=backref("user", lazy="bulk"),
                    lazy="bulk",
                    order_by=[desc(addresses.c.email_address)],
                ),
                "children": relationship(
                    User,
                    backref=backref("parent", remote_side=[users.c.id], lazy="bulk"),
                    lazy="bulk",
                ),
                "user_info": relationship(
                    UserInfo,
                    lazy="bulk",
                    backref=backref("user", lazy="bulk"),
                    uselist=False,
                ),
                "things": relationship(
                    Thing, secondary=cls.tables.user_to_things, lazy="bulk"
                ),
            },
        )
        mapper(Address, addresses)
        mapper(UserInfo, user_infos)
        mapper(
            Thing,
            things,
            properties={
                "users": relationship(
                    User,
                    secondary=cls.tables.user_to_things,
                    lazy="bulk",
                    overlaps="things",
                ),
            },
        )

        configure_mappers()

    @classmethod
    def define_tables(cls, metadata):
        Table(
            "users",
            metadata,
            Column("id", Integer, primary_key=True, test_needs_autoincrement=True),
            Column("name", String(30), nullable=False),
            Column("parent_id", None, ForeignKey("users.id")),
            test_needs_acid=True,
            test_needs_fk=True,
        )

        Table(
            "user_infos",
            metadata,
            Column("id", Integer, primary_key=True, test_needs_autoincrement=True),
            Column("details", Text),
            Column("user_id", None, ForeignKey("users.id")),
            test_needs_acid=True,
            test_needs_fk=True,
        )

        Table(
            "addresses",
            metadata,
            Column("id", Integer, primary_key=True, test_needs_autoincrement=True),
            Column("user_id", None, ForeignKey("users.id")),
            Column("email_address", String(50), nullable=False),
            test_needs_acid=True,
            test_needs_fk=True,
        )

        Table(
            "things",
            metadata,
            Column("id", Integer, primary_key=True, test_needs_autoincrement=True),
            Column("name", String(30), nullable=False),
            test_needs_acid=True,
            test_needs_fk=True,
        )

        Table(
            "user_to_things",
            metadata,
            Column("user_id", None, ForeignKey("users.id")),
            Column("thing_id", None, ForeignKey("things.id")),
            test_needs_acid=True,
            test_needs_fk=True,
        )

    @classmethod
    def fixtures(cls):
        return {
            "users": (
                ("id", "name", "parent_id"),
                (7, "jack", None),
                (8, "jack jr", 7),
                (9, "fred", 7),
                (10, "jack jr jr", 8),
            ),
            "user_infos": (
                ("id", "user_id", "details"),
                (1, 7, "is cool"),
                (2, 8, "is not cool"),
                (3, 10, "is moderately cool"),
            ),
            "addresses": (
                ("id", "user_id", "email_address"),
                (1, 7, "jack@bean.com"),
                (2, 8, "jackjr@wood.com"),
                (3, 8, "jackjr@bettyboop.com"),
                (4, 8, "jackjr@lala.com"),
                (5, 9, "fred@fred.com"),
            ),
            "things": (("id", "name"), (1, "dog"), (2, "lamp"), (3, "chair")),
            "user_to_things": (
                ("user_id", "thing_id"),
                (7, 1),
                (8, 1),
                (8, 1),  # include a duplicate intentionally
                (10, 2),
                (9, 2),
                (10, 3),
            ),
        }
