from nose2 import events, session
from nose2.tests._common import TestCase


class Example(events.Plugin):
    commandLineSwitch = ("X", "xxx", "triple x")

    def testOutcome(self, event):
        pass


class TestPluginApi(TestCase):
    def setUp(self):
        self.session = session.Session()
        self.plug = Example(session=self.session)
        super(TestCase, self).setUp()

    def test_add_option_adds_option(self):
        helpt = self.session.argparse.format_help()
        assert "-X" in helpt and "--xxx" in helpt, (
            "commandLineSwitch arg not found in help text: %s" % helpt
        )

    def test_short_opt_registers_plugin(self):
        args, argv = self.session.argparse.parse_known_args(["-X"])
        assert self.plug in self.session.plugins
        assert (
            self.plug in self.session.hooks.testOutcome.plugins
        ), "short opt did not register plugin"

    def test_long_opt_registers_plugin(self):
        args, argv = self.session.argparse.parse_known_args(["--xxx"])
        assert self.plug in self.session.plugins
        assert (
            self.plug in self.session.hooks.testOutcome.plugins
        ), "long opt did not register plugin"


class TestPluginHookOrder(TestCase):
    def make_plugin(self, module, label, handled=False):
        class OrderedPlugin(events.Plugin):
            configSection = label
            commandLineSwitch = (None, label, label)

            def startTestRun(self, event):
                event.metadata["calls"].append(label)
                event.handled = handled
                return label

        OrderedPlugin.__module__ = module
        return OrderedPlugin

    def test_activation_source_does_not_change_module_order(self):
        for configured, arguments in (
            (("alpha", "beta"), []),
            ((), ["--alpha", "--beta"]),
            ((), ["--beta", "--alpha"]),
            (("beta",), ["--alpha"]),
        ):
            with self.subTest(configured=configured, arguments=arguments):
                sess = session.Session()
                for section in configured:
                    sess.config.add_section(section)
                    sess.config.set(section, "always-on", "true")
                self.make_plugin("example.alpha", "alpha")(session=sess)
                self.make_plugin("example.beta", "beta")(session=sess)
                sess.argparse.parse_args(arguments)
                event = events.Event(calls=[])
                sess.hooks.startTestRun(event)
                self.assertEqual(event.metadata["calls"], ["alpha", "beta"])

    def test_first_module_to_handle_event_returns_its_result(self):
        sess = session.Session()
        beta = self.make_plugin("example.beta", "beta", handled=True)(session=sess)
        alpha = self.make_plugin("example.alpha", "alpha", handled=True)(session=sess)
        beta.register()
        alpha.register()
        event = events.Event(calls=[])
        self.assertEqual(sess.hooks.startTestRun(event), "alpha")
        self.assertEqual(event.metadata["calls"], ["alpha"])

    def test_repeated_registration_does_not_duplicate_calls(self):
        sess = session.Session()
        plugin = self.make_plugin("example.alpha", "alpha")(session=sess)
        plugin.register()
        plugin.register()
        event = events.Event(calls=[])
        sess.hooks.startTestRun(event)
        self.assertEqual(event.metadata["calls"], ["alpha"])

    def test_same_module_preserves_registration_order(self):
        sess = session.Session()
        beta = self.make_plugin("example.shared", "beta")(session=sess)
        alpha = self.make_plugin("example.shared", "alpha")(session=sess)
        type(beta).__name__ = type(beta).__qualname__ = "Beta"
        type(alpha).__name__ = type(alpha).__qualname__ = "Alpha"
        beta.register()
        alpha.register()
        event = events.Event(calls=[])
        sess.hooks.startTestRun(event)
        self.assertEqual(event.metadata["calls"], ["beta", "alpha"])

    def test_registration_during_dispatch_applies_to_next_event(self):
        sess = session.Session()
        added = self.make_plugin("example.alpha", "added")(session=sess)

        class RegisteringPlugin(events.Plugin):
            __module__ = "example.beta"

            def startTestRun(self, event):
                event.metadata["calls"].append("first")
                added.register()

        RegisteringPlugin(session=sess).register()
        first = events.Event(calls=[])
        sess.hooks.startTestRun(first)
        self.assertEqual(first.metadata["calls"], ["first"])
        second = events.Event(calls=[])
        sess.hooks.startTestRun(second)
        self.assertEqual(second.metadata["calls"], ["added", "first"])
