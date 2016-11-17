import asyncio
import logging
import inspect
import re
from collections import namedtuple
from .api.objects import Update

TelegramChat = namedtuple('TelegramChat', ['queue', 'handler'])

class TelegramBotCore(object):

    default_queue_size = 10

    def __init__(self, bot, api_client):
        self.bot = bot
        self.api_client = api_client
        self._dispatcher = self.dispatcher()
        self._dispatcher.send(None)
        self._chats = {}
        self._log = logging.getLogger(__name__)

    @asyncio.coroutine
    def message_handler(self, queue):
        return NotImplementedError

    def create_queue(self, maxsize=None):
        '''
        Create a new queue

        :param maxsize: the maximum size of the queue
        :return: the new queue object
        '''
        if maxsize is None:
            maxsize = self.default_queue_size
        return asyncio.Queue(maxsize)

    @asyncio.coroutine
    def dispatcher(self):
        while True:

            # Obtain Update
            update = yield
            assert isinstance(update, Update)

            # Filter the incoming update types
            # TODO: add more message handling cases
            if not 'message' in update:
                self._log.debug('discarding update {}'.format(update))
                continue

            # Get Chat object
            message = update['message']
            chat_id = message['chat']['id']
            if chat_id not in self._chats:
                self._log.debug('creating chat {}'.format(chat_id))
                queue = self.create_queue()
                handler = self.message_handler(queue)
                task = asyncio.ensure_future(handler)
                chat = TelegramChat(queue, task)
                self._chats[chat_id] = chat
            else:
                chat = self._chats[chat_id]

            # Wait if queue is full
            while chat.queue.full():
                self._log.warning('queue is full for chat_id {}'.format(chat_id))
                yield from asyncio.sleep(1)

            # Enqueue the message
            chat.queue.put_nowait(message)

    @asyncio.coroutine
    def handle_update(self, update):
        self._dispatcher.send(update)
        yield from asyncio.sleep(0)


class TelegramBotSimpleCommandCore(TelegramBotCore):

    def __init__(self, bot, api_client):
        TelegramBotCore.__init__(self, bot, api_client)
        self._log = logging.getLogger(__name__)
        # Init Commands
        self._commands = {}
        self._help = {}
        for name, function in self.get_commands():
            self.register_command(name, function)

    @asyncio.coroutine
    def message_handler(self, queue):
        context = None
        while True:
            message = yield from queue.get()
            self._log.info('handling {}'.format(message))
            text = message.get('text')
            if text is None:
                self._log.debug('no text in message')
                continue
            chat_id = message['chat']['id']

            try:
                # New command
                if text.startswith('/'):
                    try:
                        cmd_gen = self.get_command(text[1:])
                        args = text.split()[1:]
                        if context is not None:
                            context.close()
                        context = cmd_gen(args)
                        yield from self.api_client.sendMessage(chat_id, next(context))
                    except KeyError:
                        yield from self.api_client.sendMessage(chat_id, 'unknown command')
                # Followup of an existing command
                elif context is not None:
                    self._log.debug('sending {} in context {}'.format(text, context))
                    yield from self.api_client.sendMessage(chat_id, context.send(text))
                # Text outside a command context
                else:
                    try:
                        cmd_gen = self.get_command('__default__')
                        args = text.split()
                        context = cmd_gen(args)
                        yield from self.api_client.sendMessage(chat_id, next(context))
                    except KeyError:
                        pass
            except StopIteration as stopiter:
                self._log.debug('end of command {}'.format(context))
                context = None
                yield from self.api_client.sendMessage(chat_id, stopiter.value)

	# Commands Part

    def get_commands(self):
        for key, value in inspect.getmembers(self, inspect.isgeneratorfunction):
            if re.match('cmd_\w+$', key):
                yield (key.replace('cmd_', ''), value)

    def get_command(self, name):
        return self._commands[name]

    def register_command(self, name, generator):
        assert inspect.isgeneratorfunction(generator)
        assert re.match('^\w+$', name)
        self._log.debug('registering command {} -> {}'.format(name, generator))
        self._commands[name] = generator
        self._help[name] = inspect.getdoc(generator)

    def register_default_command(self, generator):
        assert inspect.isgeneratorfunction(generator)
        self._commands['__default__'] = generator

	# Pre-defined commands

    @asyncio.coroutine
    def cmd_help(self, args):
        '''
        get help about this bot commands
        '''
        return '\n'.join(['Sure! Here\'s what i can do:', ''] +
                         ['/{} - {}'.format(func, doc or '(no description)')
                          for func, doc in sorted(self._help.items())
                          if not (func.startswith('_') or func in ('start', 'stop'))])
        yield
