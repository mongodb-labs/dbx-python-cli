from bson import ObjectId
from telepath import Adapter, register


class ObjectIdAdapter(Adapter):
    """Serialize MongoDB ObjectId as its hex string for telepath/JS."""

    def build_node(self, obj, context):
        return context.build_node(str(obj))


register(ObjectIdAdapter(), ObjectId)
