from __future__ import annotations

import html
import math
from typing import TYPE_CHECKING, Final, Literal

from funpayhub.lib.telegram.ui import Menu, Button, MenuContext, KeyboardBuilder
from funpayhub.lib.telegram.ui.types import MenuBuilder, MenuModification
from funpayhub.lib.base_app.telegram.app.ui.callbacks import OpenMenu
from funpayhub.lib.base_app.telegram.app.ui.ui_finalizers import (
    StripAndNavigationFinalizer,
    build_view_navigation_btns,
)

from .callbacks import SaveExecCode, SendExecFile


if TYPE_CHECKING:
    from exec_plugin.src.types import (
        ExecutionResult as ExecR,
        ExecRegistry as ExecRReg,
    )


MAX_TEXT_LEN: Final = 3000


async def exec_view_kb(ctx: MenuContext, mode: Literal['output', 'code']) -> KeyboardBuilder:
    keyboard = KeyboardBuilder()
    keyboard.add_callback_button(
        button_id='download_exec_files',
        text='🔲 Код' if mode == 'output' else '📄 Вывод',
        callback_data=OpenMenu(
            menu_id='exec_code' if mode == 'output' else 'exec_output',
            data={'exec_id': ctx.data['exec_id']},
            ui_history=ctx.ui_history,
        ).pack(),
    )

    keyboard.add_row(
        Button.callback_button(
            button_id='exec_switch_code_output',
            text='💾 Скачать',
            callback_data=SendExecFile(exec_id=ctx.data['exec_id']).pack(),
        ),
        Button.callback_button(
            button_id='save_to_dict',
            text='💿 Сохранить',
            callback_data=SaveExecCode(exec_id=ctx.data['exec_id']).pack(),
        ),
    )

    return keyboard


async def exec_view_text(ctx: MenuContext, result: ExecR, mode: Literal['output', 'code']) -> str:
    view_text = result.output if mode == 'output' else result.code
    first = ctx.view_page * MAX_TEXT_LEN
    last = first + MAX_TEXT_LEN
    text = '<pre>' + html.escape(view_text[first:last]) + '</pre>'
    return f"""<b><u>Исполнение {result.id}</u></b>

{
        f'✅ Исполнение длилось {result.execution_time} секунд.'
        if not result.error
        else f'❌ Исполнение длилось {result.execution_time} секунд и завершилось ошибкой.'
    }

<b><u>{'Вывод' if mode == 'output' else 'Код'} исполнения:</u></b>
{text}"""


# menus
class ExecListMenuBuilder(MenuBuilder, menu_id='exec_list', context_type=MenuContext):
    async def build(self, ctx: MenuContext, exec_registry: ExecRReg) -> Menu:
        keyboard = KeyboardBuilder()

        for exec_id, result in exec_registry.registry.items():
            keyboard.add_callback_button(
                button_id=f'open_exec_output:{exec_id}',
                text=f'{"❌" if result.error else "✅"} {exec_id}',
                callback_data=OpenMenu(
                    menu_id='exec_output',
                    data={'exec_id': exec_id},
                    ui_history=ctx.as_ui_history(),
                ).pack(),
            )

        return Menu(
            main_text='Exec registry',
            main_keyboard=keyboard,
            finalizer=StripAndNavigationFinalizer(),
        )


class ExecOutputMenuBuilder(MenuBuilder, menu_id='exec_output', context_type=MenuContext):
    async def build(self, ctx: MenuContext, exec_registry: ExecRReg) -> Menu:
        result = exec_registry.registry[ctx.data['exec_id']]
        total_pages = math.ceil(result.output_len / MAX_TEXT_LEN)

        return Menu(
            main_text=await exec_view_text(ctx, result, 'output'),
            header_keyboard=await build_view_navigation_btns(ctx, total_pages),
            main_keyboard=await exec_view_kb(ctx, 'output'),
            finalizer=StripAndNavigationFinalizer(),
        )


class ExecCodeMenuBuilder(MenuBuilder, menu_id='exec_code', context_type=MenuContext):
    async def build(self, ctx: MenuContext, exec_registry: ExecRReg) -> Menu:
        result = exec_registry.registry[ctx.data['exec_id']]
        total_pages = math.ceil(result.code_len / MAX_TEXT_LEN)

        return Menu(
            main_text=await exec_view_text(ctx, result, 'code'),
            header_keyboard=await build_view_navigation_btns(ctx, total_pages),
            main_keyboard=await exec_view_kb(ctx, 'code'),
            finalizer=StripAndNavigationFinalizer(),
        )


# Main Menu Modification
class MainMenuModification(MenuModification, modification_id='exec:main_menu_modification'):
    async def modify(self, ctx: MenuContext, menu: Menu) -> Menu:
        menu.main_keyboard.add_callback_button(
            button_id='open_exec_registry',
            text='💻 Exec Registry',
            callback_data=OpenMenu(
                menu_id='exec_list',
                ui_history=ctx.as_ui_history(),
            ).pack(),
        )

        return menu
