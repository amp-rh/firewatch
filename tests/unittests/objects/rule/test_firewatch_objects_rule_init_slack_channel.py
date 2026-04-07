import unittest

from src.objects.rule import Rule


class TestRuleInitSlackChannel(unittest.TestCase):
    def setUp(self):
        self.rule_dict = {
            "jira_project": "project1",
            "jira_epic": "epic1",
            "jira_component": ["component1"],
            "jira_affects_version": "version1",
            "jira_additional_labels": ["label1"],
            "jira_assignee": "assignee1@email.com",
            "jira_priority": "Blocker",
        }

    def test_rule_init_with_slack_channel(self):
        rule_dict = {**self.rule_dict, "slack_channel": "#test-channel"}
        rule = Rule(rule_dict=rule_dict)
        assert rule.slack_channel == "#test-channel"

    def test_rule_init_without_slack_channel(self):
        rule = Rule(rule_dict=self.rule_dict)
        assert rule.slack_channel is None
