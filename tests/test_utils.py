"""Util tests"""
import os
import unittest
from viktor.utils import Viktor


bot_name = 'viktor'
key_path = os.path.join(os.path.expanduser('~'), 'keys')
key_dict = {}
for t in ['SIGNING_SECRET', 'XOXB_TOKEN', 'XOXP_TOKEN', 'VERIFY_TOKEN']:
    with open(os.path.join(key_path, f'{bot_name.upper()}_SLACK_{t}')) as f:
        key_dict[t.lower()] = f.read().strip()


class TestViktor(unittest.TestCase):
    vika = Viktor(bot_name, key_dict['xoxb_token'], key_dict['xoxp_token'])
    user_me = 'UM35HE6R5'  # me
    test_channel = 'CM376Q90F'   # test
    trigger = vika.triggers[0]

    def test_roles(self):
        """Test methods involving roles"""
        self.assertTrue(self.vika.collect_roleplayers().shape[0] > 0)
        self.vika.write_roles()
        self.vika.build_role_txt(channel='CM376Q90F')

    def test_compliments(self):
        msgs = [' me', ' Capital Test', ' Põder, kes põõnab põõsas',
                ' мои друг Наташа', ' doot doot -indeed', 'NoSpaces']
        for msg in msgs:
            comp = self.vika.compliment(f'compliment{msg}', self.user_me)
            self.vika.st.send_message('test', comp)

    def test_insults(self):
        msgs = [' me', ' Capital Test', ' мои друг Валерий', ' doot doot -i', 'NoSpaces']
        for msg in msgs:
            comp = self.vika.insult(f'insult {msg}')
            self.vika.st.send_message('test', comp)
