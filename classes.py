class PrivateRoom:
    def __init__(self):
        self.guild_id = None
        self.owner_id = None
        self.private_voice_id = None
        self.private_text_id = None
        self.waiting_room_id = None


class DeleteProcess:
    def __init__(self):
        self.doer_id = None
        self.start_msg_id = None
        self.end_msg_id = None