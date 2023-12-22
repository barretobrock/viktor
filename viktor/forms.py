from slacktools.block_kit.base import BlocksType
from slacktools.block_kit.blocks import (
    ActionsBlock,
    ImageBlock,
    MarkdownContextBlock,
    MarkdownSectionBlock,
    PlainTextHeaderBlock,
    PlainTextInputBlock,
    UserSelectSectionBlock,
)
from slacktools.block_kit.elements.display import PlainTextElement
from slacktools.block_kit.elements.input import (
    ButtonElement,
    DispatchActionConfigElement,
)


class Forms:
    """Stores various Block Kit forms"""

    @classmethod
    def build_main_menu(cls, user: str, channel: str) -> BlocksType:
        """Generates and sends a main menu"""
        button_list = [
            ButtonElement('Phrase', value='phrase', action_id='phrase'),
            ButtonElement('Insult', value='insult', action_id='insult'),
            ButtonElement('OKR Roles', value='roles', action_id='roles'),
            ButtonElement('OKR Perks!', value='perks', action_id='perks'),
            cls.cancel_button()
        ]
        return [
            PlainTextHeaderBlock('Velkom zu Wiktor Main Menu'),
            ActionsBlock(button_list),
        ]

    @staticmethod
    def cancel_button() -> ButtonElement:
        return ButtonElement('Cancel!!!', value='cancel', action_id='make-cancel')

    @staticmethod
    def build_new_emoji_form_p1() -> BlocksType:
        """Intakes a link to the new emoji"""
        return [
            PlainTextInputBlock(label='Insert emoji URL here uwu', action_id='new-emoji-p1')
        ]

    @classmethod
    def build_new_emoji_form_p2(cls, url: str, suggested_name: str) -> BlocksType:
        """Builds the second part to the new game form with Block Kit"""
        dispatch = DispatchActionConfigElement(trigger_on_enter_pressed=True)
        return [
            ImageBlock(url, suggested_name, title=PlainTextElement('Here\'s how your emoji will look...')),
            PlainTextInputBlock(label='Type the name of the emoji without ":"',
                                initial_value=suggested_name, action_id='new-emoji-p2', dispatch_action_elem=dispatch),
            ActionsBlock([cls.cancel_button()])
        ]

    @staticmethod
    def build_ifact_input_form_p1() -> BlocksType:
        """Intakes a link to the new emoji"""
        dispatch = DispatchActionConfigElement(trigger_on_enter_pressed=True)
        return [
            PlainTextInputBlock('Add the fact here!', action_id='new-ifact', dispatch_action_elem=dispatch)
        ]

    @staticmethod
    def build_update_user_level_form() -> BlocksType:
        return [
            PlainTextHeaderBlock('Levelup form!'),
            MarkdownContextBlock('_(yes, it really is this easy to levelup!)_'),
            UserSelectSectionBlock('Select user to levelup', action_id='levelup-user')
        ]

    @staticmethod
    def build_update_user_ltits_form_p1() -> BlocksType:
        return [
            PlainTextHeaderBlock('LTITs distribution form, part 1!'),
            MarkdownContextBlock('_(yes, it really is this easy to get LTITs!)_'),
            UserSelectSectionBlock('Select user to give LTITs to', action_id='ltits-user-p1')
        ]

    @classmethod
    def build_update_user_ltits_form_p2(cls, current_ltits: float) -> BlocksType:
        dispatch = DispatchActionConfigElement(trigger_on_enter_pressed=True)
        return [
            PlainTextHeaderBlock('LTITs distribution form, part 2!'),
            MarkdownContextBlock('_(yes, it really is this easy to get LTITs!)_'),
            MarkdownContextBlock(f'User\'s current LTITs: *`{current_ltits}`*'),
            PlainTextInputBlock('Select LTIT amount', action_id='ltits-user-p2', initial_value=str(10),
                                dispatch_action_elem=dispatch),
            ActionsBlock([cls.cancel_button()])
        ]

    @classmethod
    def build_role_input_form_p1(cls, existing_title: str) -> BlocksType:
        """Intakes a link to the new emoji"""
        dispatch = DispatchActionConfigElement(trigger_on_enter_pressed=True)
        return [
            PlainTextHeaderBlock('Form 420-KEKW: Self-professed ReOrg Pending Approval from Viktor, Part 1'),
            PlainTextInputBlock(label='What\'s your desired new title here at OKR?',
                                action_id='new-role-p1', initial_value=existing_title, multiline=True,
                                dispatch_action_elem=dispatch),
            ActionsBlock([cls.cancel_button()])
        ]

    @classmethod
    def build_role_input_form_p2(cls, title: str, existing_desc: str) -> BlocksType:
        """Intakes a link to the new emoji"""
        dispatch = DispatchActionConfigElement(trigger_on_enter_pressed=True)
        return [
            PlainTextHeaderBlock('Form 420-W: Self-professed ReOrg Pending Approval from Viktor, Part 2'),
            MarkdownSectionBlock(':uwupolice:*Your new title*:'),
            MarkdownSectionBlock(title),
            PlainTextInputBlock(
                label='Now, Describe your new title - like, what would you say... you do here?',
                action_id='new-role-p2', initial_value=existing_desc, multiline=True, dispatch_action_elem=dispatch),
            ActionsBlock([cls.cancel_button()])
        ]
