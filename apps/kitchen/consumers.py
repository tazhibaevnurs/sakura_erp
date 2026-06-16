import json

from channels.generic.websocket import AsyncWebsocketConsumer


class KitchenConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.section_slug = self.scope["url_route"]["kwargs"]["section_slug"]
        self.group_name = f"kitchen_{self.section_slug}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def new_order_item(self, event):
        await self.send(text_data=json.dumps(event["data"]))
