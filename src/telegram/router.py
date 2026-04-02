from __future__ import annotations

import os
import json
import time
import textwrap
import traceback
import contextlib
from typing import Any
from io import StringIO
from copy import copy
from pathlib import Path

from aiogram import Router
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InputMediaDocument
from aiogram.filters import Command
from exec_plugin.src.types import ExecutionResult, ExecRegistry

from funpayhub.lib.telegram.ui import MenuContext

from .callbacks import SaveExecCode, SendExecFile


r = Router(name='exec_plugin')


async def execute_code(
    registry: ExecRegistry,
    exec_id: str | None,
    code: str,
    execution_dict: dict[str, Any],
) -> ExecutionResult:
    temp_buffer = StringIO()
    error = False

    a = time.time()
    with contextlib.redirect_stdout(temp_buffer):
        with contextlib.redirect_stderr(temp_buffer):
            try:
                glob = copy(globals())
                glob.update(execution_dict)
                # glob.update(data, message=message, buffer=temp_buffer)
                wrapped_code = f'async def __wrapper_function__():\n{textwrap.indent(code, "  ")}'
                _locals: dict[str, Any] = {}
                exec(wrapped_code, glob, _locals)
                fn = _locals['__wrapper_function__']
                fn.__globals__.update(glob)
                await fn()
            except:
                error = True
                traceback.print_exc()
    execution_time = time.time() - a

    return registry.add_result(
        id=exec_id,
        code=code,
        output=temp_buffer.getvalue(),
        error=error,
        execution_time=execution_time,
    )


@r.message(Command('execlist'))
async def exec_list_menu(message: Message):
    await MenuContext(menu_id='exec_list', trigger=message).answer_to()


@r.message(Command('exec'))
async def execute_python_code(m: Message, exec_registry: ExecRegistry, **kwargs: Any) -> Any:
    text = m.text or m.caption
    split = text.split('\n', maxsplit=1)
    command = split[0].strip().split(maxsplit=1)
    exec_id = command[1] if len(command) > 1 else None
    source = split[1].strip() if len(split) > 1 else None

    if not exec_id and not source:
        return m.answer(
            'Укажите ID исполнения на одной строке с /exec или код исполнения с новой строки.',
        )

    if exec_id and not source:
        path = Path(exec_id)
        if path.exists() and path.is_file():
            with path.open('r', encoding='utf-8') as f:
                source = f.read()

        else:
            if exec_id not in exec_registry.registry:
                return m.answer(f'Исполнение {exec_id!r} не найдено.')
            source = exec_registry.registry[exec_id].code
        exec_id = None

    data = kwargs | {'message': m, 'exec_registry': exec_registry}
    r = await execute_code(exec_registry, exec_id, source, data)
    await MenuContext(menu_id='exec_output', trigger=m, data={'exec_id': r.id}).answer_to()


@r.callback_query(SendExecFile.filter())
async def send_exec_file(q: CallbackQuery, exec_registry: ExecRegistry, cbd: SendExecFile) -> Any:
    result = exec_registry.registry[cbd.exec_id]
    files = []

    if 0 < result.code_size <= 51380224:
        files.append(
            InputMediaDocument(
                media=BufferedInputFile(result.code.encode(), filename='code.py'),
                caption=f'Код исполнения {result.id}',
            ),
        )
    if 0 < result.output_size <= 51380224:
        files.append(
            InputMediaDocument(
                media=BufferedInputFile(result.output.encode(), filename='output.txt'),
                caption=f'Вывод выполнения {cbd.exec_id}',
            ),
        )

    if not files:
        return q.answer(text='Размеры файлов слишком большие.', show_alert=True)

    await q.answer(
        text='Выгрузка файлов началась. Это может занять некоторое время.',
        show_alert=True,
    )

    await q.message.answer_media_group(media=files)


@r.callback_query(SaveExecCode.filter())
async def save_exec(q: CallbackQuery, exec_registry: ExecRegistry, cbd: SaveExecCode) -> None:
    result = exec_registry.registry[cbd.exec_id]
    os.makedirs(f'.exec/{cbd.exec_id}', exist_ok=True)
    with open(f'.exec/{cbd.exec_id}/exec.json', 'w', encoding='utf-8') as f:
        f.write(
            json.dumps(
                {
                    'code': result.code,
                    'output': result.output,
                    'error': result.error,
                    'execution_time': result.execution_time,
                },
                ensure_ascii=False,
            ),
        )

    await q.answer(f'Данные исполнения сохранены в .exec/{cbd.exec_id}/exec.json.')
