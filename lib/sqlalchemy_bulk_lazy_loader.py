from sqlalchemy import util, inspect, Column
from sqlalchemy.orm import properties, attributes, interfaces, strategy_options
from sqlalchemy.orm.strategies import LazyLoader
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList
from sqlalchemy.sql import operators


class UnsupportedRelationError(Exception):
    """Error to use if a relationship can't be loaded by this lazy loader"""


class BulkLazyLoader(LazyLoader):

    def __init__(self, parent, strategy_key):
        super(BulkLazyLoader, self).__init__(parent, strategy_key)
        criterion, param_keys = self._simple_lazy_clause
        self._criterion = criterion
        self._join_col = self._get_join_col_from_criterion(criterion)
        self._validate_relation()
        param_key = param_keys[0]
        self._ident = param_key[1]

    @classmethod
    def register_loader(cls):
        """
        call this method before defining any mappers to make this loader available with `lazy="bulk"`
        """
        decorator = properties.RelationshipProperty.strategy_for(lazy="bulk")
        decorator(cls)

    def _get_join_col_from_criterion(self, criterion, reverse=False):
        """
        Criterion is the filter clause used by the LazyLoader base class. It's of the form `:param = Model.column_id`
        This method extracts the Model.column_id so we can make our own `Model.column_id IN :param` bulk query
        """

        if isinstance(criterion, BooleanClauseList):
            for clause in criterion.clauses:
                col = self._get_join_col_from_criterion(clause)
                if col is not None:
                    return col
        elif isinstance(criterion, BinaryExpression):
            if isinstance(criterion.left, Column) and isinstance(criterion.right, BindParameter):
                return criterion.left
            elif isinstance(criterion.right, Column) and isinstance(criterion.left, BindParameter):
                return criterion.right
        return None

    def _clause_has_no_parameters(self, clause):
        return not isinstance(clause.left, BindParameter) and not isinstance(clause.right, BindParameter)

    def _get_similar_unpopulated_models(self, model, session):
        """
        This finds all other models of this class in the session that also need to have this relationship lazyloaded
        """
        model_class = model.__class__
        dict_ = attributes.instance_dict(model)
        similar_models = []
        for possible_model in session.identity_map.values():
            is_same_class = isinstance(possible_model, model_class)
            is_not_new = possible_model not in session.new
            if is_same_class and is_not_new and self.key not in attributes.instance_dict(possible_model):
                similar_models.append(possible_model)
        return similar_models

    def _get_model_value(self, model, mapper, col, passive):
        state = inspect(model)
        dict_ = attributes.instance_dict(model)

        # not sure what this means, taken from LazyLoader#_generate_lazy_clause
        if passive & attributes.INIT_OK:
            passive ^= attributes.INIT_OK

        # adapted from LazyLoader#_generate_lazy_clause
        if passive and passive & attributes.LOAD_AGAINST_COMMITTED:
            return mapper._get_committed_state_attr_by_column(state, dict_, col, passive)
        return mapper._get_state_attr_by_column(state, dict_, col, passive)

    def _extract_non_list_result(self, result):
        """logic copied from LazyLoader#_emit_lazyload"""
        l = len(result)
        if l:
            if l > 1:
                util.warn(
                    "Multiple rows returned with "
                    "uselist=False for lazily-loaded attribute '%s' "
                    % self.parent_property)

            return result[0]
        else:
            return None

    def _set_results_on_models(self, param_value_to_results, param_value_to_models, current_model):
        current_model_result = None
        for value, models in param_value_to_models.items():
            for model in models:
                result = param_value_to_results.get(value, [])
                # ensure models aren't given identical result lists so modifying results in one doesn't modify others
                result = result[:]
                if not self.uselist:
                    result = self._extract_non_list_result(result)
                if model == current_model:
                    current_model_result = result
                attributes.set_committed_value(model, self.key, result)
        return current_model_result

    def _unsupported_relation(self):
        model_name = self.parent_property.parent.class_.__name__
        error_msg = (
            'BulkLazyLoader {}.{}: '.format(model_name, self.key) +
            'Only simple relations on 1 primary key and without custom joins are supported'
        )
        raise UnsupportedRelationError(error_msg)

    def _validate_relation(self):
        criterion, param_keys = self._simple_lazy_clause
        if self.parent_property.secondary is None:
            # for relationship without a secondary join criterion should look like: "COL = :param"
            if not isinstance(criterion, BinaryExpression):
                self._unsupported_relation()
        else:
            # for relationship with a secondary join criterion should look like: "T1.col1 = :param AND T1.col2 = T2.col"
            if not isinstance(criterion, BooleanClauseList):
                self._unsupported_relation()
            if criterion.operator is not operators.and_:
                self._unsupported_relation()
            for clause in criterion.clauses:
                if not isinstance(clause, BinaryExpression):
                    self._unsupported_relation()

        if self._join_col is None:
            self._unsupported_relation()

        if len(param_keys) != 1:
            self._unsupported_relation()

        key, ident, value = param_keys[0]
        if value is not None or ident is None:
            self._unsupported_relation()

    def _emit_lazyload(self, session, state, ident_key, passive):
        """
        This is the main method from LazyLoader we need to overwrite. Unfortunately I don't think there's
        a clean way to add bulk functionality without partially copy/pasting from LazyLoader#_emit_lazyload
        """

        q = session.query(self.mapper, self._join_col)._adapt_all_clauses()

        # -------------- COPIED/MODIFIED FROM LAZYLOADER -----------------

        if self.parent_property.secondary is not None:
            q = q.select_from(self.mapper, self.parent_property.secondary)

        q = q._with_invoke_all_eagers(False)

        if passive & attributes.NO_AUTOFLUSH:
            q = q.autoflush(False)

        if self.parent_property.order_by:
            q = q.order_by(*util.to_list(self.parent_property.order_by))

        for rev in self.parent_property._reverse_property:
            # reverse props that are MANYTOONE are loading *this*
            # object from get(), so don't need to eager out to those.
            if rev.direction is interfaces.MANYTOONE and \
                rev._use_get and \
                    not isinstance(rev.strategy, LazyLoader):
                q = q.options(
                    strategy_options.Load.for_existing_path(
                        q._current_path[rev.parent]
                    ).lazyload(rev.key)
                )

        # ------------ CUSTOM BULK LOGIC --------------------------

        parent_mapper = self.parent_property.parent
        current_model = state.obj()
        # Find all models in this session that also need this same relationship to be populated
        similar_models = self._get_similar_unpopulated_models(current_model, session)
        param_value_to_models = {}
        param_values = []
        for model in similar_models:
            value = self._get_model_value(model, col=self._ident, mapper=parent_mapper, passive=passive)
            param_value_to_models[value] = param_value_to_models.get(value, [])
            param_value_to_models[value].append(model)
            param_values.append(value)

        if self.parent_property.secondary is not None:
            # if there's a secondary join, we want to just replace the first join clause in the filter
            # and still leave the rest of the clauses as is. ex if we have:
            # "Image".id = "MessageToImage".image_id AND "MessageToImage".message_id = :param1
            # We want to make sure we still include "Image".id = "MessageToImage".image_id in our query
            for clause in self._criterion.clauses:
                if self._clause_has_no_parameters(clause):
                    q = q.filter(clause)

        # This is the core change from plain LazyLoader - use `Model.field IN (values)` instead of `Model.field = value`
        q = q.filter(self._join_col.in_(param_values))
        results = q.all()

        param_value_to_results = {}
        for result in results:
            # we selected from both the model table and join col, so results are tuples of (model, join_col_value)
            (result_model, join_col_value) = result
            param_value_to_results[join_col_value] = param_value_to_results.get(join_col_value, [])
            param_value_to_results[join_col_value].append(result_model)

        current_model_result = self._set_results_on_models(param_value_to_results, param_value_to_models, current_model)
        # The loader expects us to return the related models for the model in question. We return that here to maintain
        # the LazyLoader interface, even though we already set all the relationships on all models directly above
        return current_model_result
