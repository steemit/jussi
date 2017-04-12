# -*- coding: utf-8 -*-
import logging
from collections.abc import MutableMapping

from async_request import dispatch

logger = logging.getLogger(__name__)


class AsyncPrefixedMethods(MutableMapping):
    """Holds a list of methods.
    """

    def __init__(self, default_namespace=None):
        self._items = {}
        self.default_namespace = default_namespace or 'steemd'

    def __getitem__(self, key):
        namespace, _ = self.split(key)
        return self._items[namespace]

    def __setitem__(self, key, value):
        # Method must be callable
        if not callable(value):
            raise TypeError('%s is not callable' % type(value))
        self._items[key] = value

    def __delitem__(self, key):
        del self._items[key]

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def split(self, namespaced_method):
        try:
            namespace, method = namespaced_method.split('.')
        except ValueError:
            namespace, method = self.default_namespace, namespaced_method
        logger.debug('%s %s', namespace, method)
        return namespace, method

    def add(self, method):
        """Register a function to the list::
            methods.add(subtract)
        Alternatively, use as a decorator::
            @methods.add
            def subtract(minuend, subtrahend):
                return minuend - subtrahend
        :param method: Function to register to the list
        :type method: Function or class method
        :raise AttributeError:
            Raised if the method being added has no name. (i.e. it has no
            ``__name__`` property, and no ``name`` argument was given.)
        """
        # If no custom name was given, use the method's __name__ attribute
        # Raises AttributeError otherwise
        namespace = method.__name__
        logger.debug('Adding method %s to namespace %s', method, namespace)
        self.update({namespace: method})
        return method

    async def dispatch(self, request):
        return await dispatch(self, request)

    def serve_forever(self):
        raise NotImplementedError()


methods = AsyncPrefixedMethods()
