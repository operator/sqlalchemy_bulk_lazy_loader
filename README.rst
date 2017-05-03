SQLAlchemy Bulk Lazy Loader
===========================

A custom lazy loader for SQLAlchemy relations which ensures relations are always loaded efficiently. This loader automatically solves the `n+1 query problem <http://use-the-index-luke.com/sql/join/nested-loops-join-n1-problem>`_ without needing to manually add ``joinedload`` or ``subqueryload`` statements to all your queries.

The Problem
-----------

The n + 1 query problem arises whenever relationships are lazy-loaded in a loop. For example:

.. code:: python

    students = session.query(Student).limit(100).all()
    for student in students:
        print('{} studies at {}'.format(student.name, student.school.name))

In the above code 101 SQL queries will be generated - one to load the list of students and then 100 individual queries for each student to load that student's school. The statements look like:

.. code:: sql

    SELECT * FROM students LIMIT 100;
    SELECT * FROM schools WHERE schools.student_id = 1 LIMIT 1;
    SELECT * FROM schools WHERE schools.student_id = 2 LIMIT 1;
    SELECT * FROM schools WHERE schools.student_id = 3 LIMIT 1;
    SELECT * FROM schools WHERE schools.student_id = 4 LIMIT 1;
    ...

This is bad.


The traditional way to solve this with SQLAlchemy is to add a ``joinedload`` or ``subqueryload`` to the initial query to include the schools along with the students, like below:

.. code:: python

    students = (
        session.query(Student)
            .options(subqueryload(Student.school))
            .limit(100)
            .all()
    )
    for student in students:
        print('{} studies at {}'.format(student.name, student.school.name))

While this works, it needs to be added to every query that's performed, and when there's a lot of related models being added you can easily end up with a massive list of ``subqueryload`` and ``joinedload``. If you forget even one anywhere then you're silently back to the n + 1 query problem. Also, if you stop needing a relation later you need to remember to remove it from the original query or else you're now loading too much data. Furthermore, it's just a huge pain to have to maintain these lists of related models throughout your code everywhere there's a database query.

Wouldn't it be great if you didn't have to worry about adding ``subqueryload`` and ``joinedload`` and yet also be guaranteed that all your relations are loading efficiently?

How The Bulk Lazy Loader Works
------------------------------

99% of the time, if there is a list of models loaded in memory and a relation on one of them is lazy-loaded then you're in a loop and the same relationship is going to be requested on every other model. SQLAlchemy Bulk Lazy Loader assumes this is the case and whenever a relation on a model is lazy-loaded, it will look through the current session for any other similar models that need that same relation loaded and will issue a single, bulk SQL statement to load them all at once.

This means you can load all the relations you want in loops while being guaranted that all relations are loaded performantly, and only the relations that are used are loaded. For example, here's the same code from above:

.. code:: python

    students = session.query(Student).limit(100).all()
    for student in students:
        print('{} studies at {}'.format(student.name, student.school.name))

The Bulk Lazy Loader will issue only 2 SQL statements, the same as if you had specified ``subqueryload`` on the initial query, except that now your code is a lot cleaner and you're guaranteed to be loading just the relations you need. Yay!

Installation
------------

SQLAlchemy Bulk Lazy Loader can be installed via pip

``pip install SQLAlchemy-bulk-lazy-loader``

Usage
-----

Before you declare your SQLAlchemy mappings you need to run the following:

.. code:: python

    from sqlalchemy_bulk_lazy_loader import BulkLazyLoader
    BulkLazyLoader.register_loader()


This registers the loader with sqlalchemy and makes it available on your relations by specifying ``lazy='bulk'`` in your relation mappings. For example:

.. code:: python

    class Student(db.model):
        id = db.Column(db.Integer, primary_key=True)
        school_id = db.Column(db.Integer, db.ForeignKey('school.id'))

    class School(db.model):
        id = db.Column(db.Integer, primary_key=True)
        students = db.relationship('Student', lazy='bulk', backref=db.backref('school', lazy='bulk'))

And that's it! The bulk lazy loader will be used for ``student.school`` and ``school.students`` relations.

Limitations
-----------

Currently only relations on a single primary key or a simple secondary join are supported.

.. code:: python

    students = relationship('Student', lazy='bulk') # OK!
    students = relationship('Student', lazy='bulk', order_by=Student.id) # OK!
    student = relationship('Student', lazy='bulk', uselist=False) # OK!
    students = relationship('Student', lazy='bulk', secondary=school_to_students) # OK!
    students = relationship('Student', lazy='bulk', secondary=school_to_students, primaryjoin='and_(...)') # NOT SUPPORTED

Python 2 is not supported.

But I have this one case where I want to load the relations differently!
------------------------------------------------------------------------

If you want to load relations in the query still using ``subqueryload`` or ``joinedload`` you can still do that - the bulk lazy loader will only kick in when it's asked for a relation on a model that isn't already loaded. If you really need fine-grained control of relation loading in a specific case you can also use ``attributes.set_committed_value(model, <relation_name>, <related_model/s>)`` to explicitly set related models. In fact this is how ``BulkLazyLoader`` works behind the scenes.

Contributing
------------

Contributions are welcome! Create a pull request and make sure to add test coverage. Tests use the SQLAlchemy test framework and can be run with ``py.test``. 

Happy loading!
