"""核心模块单元测试 - 覆盖时间解析、id_bind提取、配置系统、token生成、错误码等。"""
import os
import sys
import json
import datetime
import unittest

os.environ["BTB_SKIP_INITIAL_TIME_SYNC"] = "1"
sys.path.insert(0, '.')


class TestParseSaleStartTime(unittest.TestCase):
    """测试开售时间解析 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import parse_sale_start_time
        self.parse = parse_sale_start_time

    def test_standard_iso_format(self):
        result = self.parse("2026-07-31T18:04:57")
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 7)
        self.assertEqual(result.day, 31)
        self.assertEqual(result.hour, 18)
        self.assertEqual(result.minute, 4)
        self.assertEqual(result.second, 57)

    def test_standard_space_format(self):
        result = self.parse("2026-07-31 18:04:57")
        self.assertEqual(result.hour, 18)
        self.assertEqual(result.minute, 4)

    def test_no_seconds(self):
        result = self.parse("2026-07-31 18:04")
        self.assertEqual(result.hour, 18)
        self.assertEqual(result.minute, 4)
        self.assertEqual(result.second, 0)

    def test_slash_format(self):
        result = self.parse("2026/07/31 18:04:57")
        self.assertEqual(result.month, 7)

    def test_english_with_cst(self):
        result = self.parse("Sat Aug 22 18:00:00 CST 2026")
        self.assertEqual(result.month, 8)
        self.assertEqual(result.day, 22)
        self.assertEqual(result.hour, 18)

    def test_english_no_tz(self):
        result = self.parse("Sat Aug 22 18:00:00 2026")
        self.assertEqual(result.month, 8)

    def test_english_no_seconds(self):
        result = self.parse("Sat Aug 22 18:00 2026")
        self.assertEqual(result.hour, 18)

    def test_beijing_timezone(self):
        result = self.parse("2026-07-31 18:00:00")
        self.assertEqual(result.utcoffset(), datetime.timedelta(hours=8))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            self.parse("")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            self.parse("not-a-date")


class TestFormatCountdown(unittest.TestCase):
    """测试倒计时格式化 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import format_countdown
        self.format = format_countdown

    def test_seconds_only(self):
        self.assertEqual(self.format(45), "0小时0分45秒")

    def test_minutes(self):
        self.assertEqual(self.format(125), "0小时2分5秒")

    def test_hours(self):
        self.assertEqual(self.format(3661), "1小时1分1秒")

    def test_days(self):
        self.assertEqual(self.format(90061), "1天1小时1分1秒")

    def test_zero(self):
        self.assertEqual(self.format(0), "0小时0分0秒")

    def test_negative_clamped(self):
        self.assertEqual(self.format(-10), "0小时0分0秒")


class TestNextCountdownReportAt(unittest.TestCase):
    """测试倒计时报告间隔 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import next_countdown_report_at
        self.next = next_countdown_report_at

    def test_over_day(self):
        self.assertEqual(self.next(100000), 86400)

    def test_over_hour(self):
        self.assertEqual(self.next(5000), 3600)

    def test_over_minute(self):
        self.assertEqual(self.next(120), 60)

    def test_over_ten_seconds(self):
        self.assertEqual(self.next(15), 10)

    def test_under_ten(self):
        self.assertEqual(self.next(5), -1)


class TestBuildTicketOption(unittest.TestCase):
    """测试票档选项构建 - interface/project.py"""

    def setUp(self):
        from interface.project import _build_ticket_option
        self.build = _build_ticket_option

    def _make_ticket(self, **overrides):
        base = {
            "id": 123,
            "price": 9000,
            "desc": "测试票",
            "sale_start": "2026-07-31 18:00:00",
            "sale_flag_number": 2,
            "static_limit": {"num": 8, "limit_option": 0, "num_type": 1},
        }
        base.update(overrides)
        return base

    def _make_screen(self, **overrides):
        base = {
            "id": 456,
            "name": "测试场次",
            "express_fee": 0,
            "project_id": 789,
        }
        base.update(overrides)
        return base

    def test_id_bind_from_project_level(self):
        """id_bind应优先使用project级传入值"""
        ticket = self._make_ticket()
        screen = self._make_screen()
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True, id_bind=2)
        self.assertEqual(option["id_bind"], 2)

    def test_id_bind_default_one(self):
        """未传入id_bind时默认为1"""
        ticket = self._make_ticket()
        screen = self._make_screen()
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True)
        self.assertEqual(option["id_bind"], 1)

    def test_id_bind_ticket_level_overrides(self):
        """ticket级有id_bind时覆盖project级(兼容旧数据)"""
        ticket = self._make_ticket(id_bind=2)
        screen = self._make_screen()
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True, id_bind=1)
        self.assertEqual(option["id_bind"], 2)

    def test_max_count_from_static_limit(self):
        ticket = self._make_ticket(static_limit={"num": 4})
        screen = self._make_screen()
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True)
        self.assertEqual(option["max_count"], 4)

    def test_max_count_fallback_eight(self):
        ticket = self._make_ticket()
        del ticket["static_limit"]
        screen = self._make_screen()
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True)
        self.assertEqual(option["max_count"], 8)

    def test_price_with_express_fee(self):
        ticket = self._make_ticket(price=9000)
        screen = self._make_screen(express_fee=1000)
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=False)
        self.assertEqual(option["price"], 10000)

    def test_eticket_no_express_fee(self):
        ticket = self._make_ticket(price=9000)
        screen = self._make_screen(express_fee=1000)
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True)
        self.assertEqual(option["price"], 9000)

    def test_display_format(self):
        ticket = self._make_ticket()
        screen = self._make_screen()
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True)
        self.assertIn("测试场次", option["display"])
        self.assertIn("测试票", option["display"])
        self.assertIn("￥90.0", option["display"])

    def test_link_id_preserved(self):
        screen = self._make_screen(link_id="link123")
        ticket = self._make_ticket()
        option = self.build(screen=screen, ticket=ticket, hot_project=False, has_eticket=True)
        self.assertEqual(option["link_id"], "link123")


class TestNormalizeNewProjectPayload(unittest.TestCase):
    """测试新接口归一化 - interface/project.py"""

    def setUp(self):
        from interface.project import _normalize_new_project_payload
        self.normalize = _normalize_new_project_payload

    def _make_payload(self, **overrides):
        base = {
            "projectId": 1004295,
            "projectName": "测试项目",
            "hotProject": False,
            "screenList": [
                {
                    "id": 1,
                    "name": "场次1",
                    "start_time": "1784736000",
                    "express_fee": 0,
                    "ticket_list": [
                        {"id": 1, "price": 9000, "desc": "票1", "sale_flag": {"number": 2}},
                    ],
                }
            ],
            "skuVenueInfo": {"name": "测试场馆", "address_detail": "测试地址"},
            "salesDates": [{"date": "2026-10-01"}],
            "endTime": 1787500799,
            "idBind": 2,
        }
        base.update(overrides)
        return base

    def test_id_bind_extracted(self):
        payload = self._make_payload(idBind=2)
        result = self.normalize(payload, 1004295)
        self.assertEqual(result["id_bind"], 2)

    def test_id_bind_default_one(self):
        payload = self._make_payload()
        del payload["idBind"]
        result = self.normalize(payload, 1004295)
        self.assertEqual(result["id_bind"], 1)

    def test_basic_fields(self):
        payload = self._make_payload()
        result = self.normalize(payload, 1004295)
        self.assertEqual(result["id"], 1004295)
        self.assertEqual(result["name"], "测试项目")
        self.assertFalse(result["hotProject"])
        self.assertEqual(len(result["screen_list"]), 1)

    def test_missing_screen_list_raises(self):
        payload = self._make_payload()
        del payload["screenList"]
        with self.assertRaises(RuntimeError):
            self.normalize(payload, 1004295)


class TestCreateOrderTerminalRule(unittest.TestCase):
    """测试订单创建终止规则 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import create_order_terminal_rule
        self.rule = create_order_terminal_rule

    def test_100003_repeat_purchase(self):
        result = self.rule(100003)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "completed")
        self.assertIn("限购", result.message)

    def test_100048_pending_order(self):
        result = self.rule(100048)
        self.assertIsNotNone(result)
        self.assertTrue(result.expose_payment_url)

    def test_100079_duplicate_order(self):
        result = self.rule(100079)
        self.assertIsNotNone(result)

    def test_non_terminal_returns_none(self):
        self.assertIsNone(self.rule(0))
        self.assertIsNone(self.rule(100051))
        self.assertIsNone(self.rule(100034))
        self.assertIsNone(self.rule(99999))


class TestIsCreateSuccess(unittest.TestCase):
    """测试创建订单成功判断 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import is_create_success
        self.is_success = is_create_success

    def test_errno_zero_success(self):
        self.assertTrue(self.is_success({"errno": 0, "msg": ""}, 0))

    def test_errno_zero_with_bbr_fails(self):
        self.assertFalse(self.is_success({"errno": 0, "msg": "defaultBBR something"}, 0))

    def test_non_zero_fails(self):
        self.assertFalse(self.is_success({"errno": 100009, "msg": "库存不足"}, 100009))


class TestExtractOrderId(unittest.TestCase):
    """测试订单ID提取 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import extract_order_id
        self.extract = extract_order_id

    def test_valid_order_id(self):
        self.assertEqual(self.extract({"data": {"orderId": "123456"}}), "123456")

    def test_none_data(self):
        self.assertIsNone(self.extract({"data": None}))

    def test_missing_data(self):
        self.assertIsNone(self.extract({}))

    def test_zero_order_id(self):
        self.assertIsNone(self.extract({"data": {"orderId": 0}}))

    def test_empty_order_id(self):
        self.assertIsNone(self.extract({"data": {"orderId": ""}}))

    def test_none_input(self):
        self.assertIsNone(self.extract(None))


class TestErrorCodes(unittest.TestCase):
    """测试错误码映射 - util/ErrorCodes.py"""

    def setUp(self):
        from util.ErrorCodes import ErrorCodes
        self.codes = ErrorCodes

    def test_known_codes(self):
        self.assertEqual(self.codes.get_message(0), "成功")
        self.assertEqual(self.codes.get_message(100009), "库存不足")
        self.assertEqual(self.codes.get_message(100051), "订单准备过期，重新验证")

    def test_unknown_code(self):
        self.assertIsNone(self.codes.get_message(99999))
        self.assertEqual(self.codes.get_message_or_unknown(99999), "未知错误码")

    def test_format_attempt_result(self):
        result = self.codes.format_attempt_result(100009, {"msg": ""})
        self.assertIn("100009", result)
        self.assertIn("库存不足", result)


class TestExtractProjectId(unittest.TestCase):
    """测试项目ID提取 - interface/common.py"""

    def setUp(self):
        from interface.common import _extract_project_id
        self.extract = _extract_project_id

    def test_numeric_input(self):
        self.assertEqual(self.extract(1004295), 1004295)
        self.assertEqual(self.extract("1004295"), 1004295)

    def test_url_with_id(self):
        self.assertEqual(
            self.extract("https://show.bilibili.com/platform/detail.html?id=1004295&from=pc_ticketlist"),
            1004295,
        )

    def test_url_no_id_raises(self):
        with self.assertRaises(ValueError):
            self.extract("https://show.bilibili.com/platform/detail.html")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            self.extract("")


class TestFormatSaleStatus(unittest.TestCase):
    """测试销售状态格式化 - interface/common.py"""

    def setUp(self):
        from interface.common import _format_sale_status
        self.format = _format_sale_status

    def test_known_flags(self):
        self.assertEqual(self.format({"sale_flag_number": 2}), "预售")
        self.assertEqual(self.format({"sale_flag_number": 4}), "售罄")
        self.assertEqual(self.format({"sale_flag_number": 101}), "未开始")

    def test_clickable_fallback(self):
        self.assertEqual(self.format({"clickable": True}), "可购买")
        self.assertEqual(self.format({"clickable": False}), "不可购买")

    def test_unknown(self):
        self.assertEqual(self.format({}), "未知状态")


class TestConfigSystem(unittest.TestCase):
    """测试配置系统 - app_cmd/config/"""

    def setUp(self):
        from app_cmd.config.BuyConfig import BuyConfig
        self.BuyConfig = BuyConfig

    def test_default_values(self):
        config = self.BuyConfig()
        self.assertEqual(config.tickets_info, "")
        self.assertEqual(config.config_file, "")
        self.assertEqual(config.time_start, "")
        self.assertEqual(config.interval, 1000)
        self.assertTrue(config.show_qrcode)
        self.assertFalse(config.use_local_token)
        self.assertEqual(config.create_retry_limit, 10)
        self.assertEqual(config.create_request_batch_size, 1)
        self.assertEqual(config.rate_limit_delay_ms, 300)

    def test_with_overrides(self):
        config = self.BuyConfig()
        modified = config.with_overrides(interval=500, tickets_info='{"test": true}')
        self.assertEqual(modified.interval, 500)
        self.assertEqual(modified.tickets_info, '{"test": true}')
        # 原对象不变
        self.assertEqual(config.interval, 1000)

    def test_from_mapping(self):
        config = self.BuyConfig.from_mapping(
            {"interval": 2000, "createRetryLimit": 5},
            source_name="db",
        )
        self.assertEqual(config.interval, 2000)
        self.assertEqual(config.create_retry_limit, 5)

    def test_to_cli_args(self):
        config = self.BuyConfig(interval=500, create_retry_limit=5)
        args = config.to_cli_args()
        self.assertIn("--interval", args)
        self.assertIn("500", args)
        self.assertIn("--create-retry-limit", args)
        self.assertIn("5", args)

    def test_apply_log_env(self):
        config = self.BuyConfig(log_level="debug")
        config.apply_log_env()
        self.assertEqual(os.environ.get("BTB_LOG_LEVEL"), "DEBUG")
        self.assertEqual(os.environ.get("BTB_CONSOLE_LOG_LEVEL"), "DEBUG")


class TestCptoken(unittest.TestCase):
    """测试ctoken生成 - cptoken/__init__.py"""

    def setUp(self):
        from cptoken import (
            generate_ctoken,
            generate_browser_window_state,
            init_ctoken_state,
            sim_ctoken_state,
        )
        self.generate_ctoken = generate_ctoken
        self.generate_browser_window_state = generate_browser_window_state
        self.init_ctoken_state = init_ctoken_state
        self.sim_ctoken_state = sim_ctoken_state

    def test_generate_ctoken_returns_base64(self):
        import base64
        token = self.generate_ctoken()
        # 应该是合法的base64
        decoded = base64.b64decode(token)
        self.assertIsInstance(decoded, bytes)
        self.assertGreater(len(decoded), 0)

    def test_generate_ctoken_deterministic_with_params(self):
        """相同参数应生成相同token"""
        t1 = self.generate_ctoken(m1=1, m2=2, m3=3, timer=10, timediff=100)
        t2 = self.generate_ctoken(m1=1, m2=2, m3=3, timer=10, timediff=100)
        self.assertEqual(t1, t2)

    def test_browser_window_state_structure(self):
        state = self.generate_browser_window_state()
        required_keys = [
            "scrollX", "scrollY", "innerWidth", "innerHeight",
            "outerWidth", "outerHeight", "screenX", "screenY",
            "screenWidth", "screenHeight", "screenAvailWidth", "screenAvailHeight",
        ]
        for key in required_keys:
            self.assertIn(key, state)

    def test_init_ctoken_state(self):
        state = self.init_ctoken_state()
        self.assertIsNotNone(state.m1)
        self.assertIsNotNone(state.m2)
        self.assertGreaterEqual(state.base_timer, 10)
        self.assertLessEqual(state.base_timer, 100)

    def test_ctoken_snapshot_generate(self):
        state = self.init_ctoken_state()
        snapshot = state.snapshot()
        prepare_token = snapshot.generate_prepare_ctoken()
        create_token = snapshot.generate_create_ctoken()
        self.assertIsInstance(prepare_token, str)
        self.assertIsInstance(create_token, str)
        # create token不包含openWindow和beforeunload，应与prepare不同
        self.assertNotEqual(prepare_token, create_token)

    def test_sim_ctoken_state(self):
        before = self.init_ctoken_state()
        after = self.sim_ctoken_state(before, now_ms=before.created_at_ms + 5000)
        self.assertIsNotNone(after)
        self.assertGreaterEqual(after.timer, before.base_timer)


class TestSanitizeFilename(unittest.TestCase):
    """测试文件名清理 - app_cmd/config_generator.py"""

    def setUp(self):
        from app_cmd.config_generator import _sanitize_filename
        self.sanitize = _sanitize_filename

    def test_removes_invalid_chars(self):
        result = self.sanitize('test:file*name?<>|')
        self.assertNotIn(':', result)
        self.assertNotIn('*', result)
        self.assertNotIn('?', result)
        self.assertNotIn('<', result)
        self.assertNotIn('>', result)
        self.assertNotIn('|', result)

    def test_normal_name_unchanged(self):
        self.assertEqual(self.sanitize("normal_name"), "normal_name")

    def test_chinese_name(self):
        result = self.sanitize("测试文件名")
        self.assertEqual(result, "测试文件名")


class TestDetectContactPhone(unittest.TestCase):
    """测试联系人手机号识别 - app_cmd/config_generator.py"""

    def setUp(self):
        from app_cmd.config_generator import _detect_contact_phone
        self.detect = _detect_contact_phone

    def test_priority_cookies_phone(self):
        result = self.detect("13800138000", {"tel": "13900139000"})
        self.assertEqual(result, "13800138000")

    def test_fallback_address_phone(self):
        result = self.detect("", {"tel": "13900139000"})
        self.assertEqual(result, "13900139000")

    def test_empty_returns_empty(self):
        result = self.detect("", {})
        self.assertEqual(result, "")

    def test_short_cookies_phone_ignored(self):
        result = self.detect("123", {"tel": "13900139000"})
        self.assertEqual(result, "13900139000")


class TestBuyStreamTypes(unittest.TestCase):
    """测试购买流数据类型 - task/buy_types.py"""

    def setUp(self):
        from task.buy_types import BuyStreamState, BuyStreamUpdate, RetryOutcome
        self.BuyStreamState = BuyStreamState
        self.BuyStreamUpdate = BuyStreamUpdate
        self.RetryOutcome = RetryOutcome

    def test_state_defaults(self):
        state = self.BuyStreamState()
        self.assertEqual(state.stage, "初始化")
        self.assertEqual(state.status, "running")
        self.assertEqual(state.countdown, "-")

    def test_update_apply_to(self):
        state = self.BuyStreamState()
        update = self.BuyStreamUpdate(stage="创建订单", attempt_current=3, attempt_total=10)
        update.apply_to(state)
        self.assertEqual(state.stage, "创建订单")
        self.assertEqual(state.attempt_current, 3)
        self.assertEqual(state.attempt_total, 10)

    def test_update_to_dict(self):
        update = self.BuyStreamUpdate(stage="测试", status="succeeded")
        d = update.to_dict()
        self.assertEqual(d["stage"], "测试")
        self.assertEqual(d["status"], "succeeded")
        self.assertNotIn("countdown", d)  # None值不包含

    def test_retry_outcome(self):
        outcome = self.RetryOutcome()
        self.assertIsNone(outcome.err)
        outcome.set_response(100009, {"msg": "库存不足"})
        self.assertEqual(outcome.err, 100009)
        self.assertIsNone(outcome.exc)


class TestBuildTokenPayload(unittest.TestCase):
    """测试token payload构建 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import build_token_payload
        self.build = build_token_payload

    def test_basic_payload(self):
        tickets_info = {
            "count": 2,
            "screen_id": 456,
            "project_id": 789,
            "sku_id": 123,
            "buyer_info": [{"name": "测试"}],
            "_prepare_buyer_info": [{"name": "测试"}],
        }
        payload = self.build(tickets_info)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["screen_id"], 456)
        self.assertEqual(payload["project_id"], 789)
        self.assertEqual(payload["sku_id"], 123)
        self.assertEqual(payload["order_type"], 1)
        self.assertTrue(payload["ignoreRequestLimit"])
        self.assertEqual(payload["requestSource"], "neul-next")

    def test_uses_prepare_buyer_info(self):
        tickets_info = {
            "count": 1, "screen_id": 1, "project_id": 1, "sku_id": 1,
            "buyer_info": "json_string",
            "_prepare_buyer_info": [{"name": "真实购票人"}],
        }
        payload = self.build(tickets_info)
        self.assertEqual(payload["buyer_info"], [{"name": "真实购票人"}])


class TestPrepareCreateRequest(unittest.TestCase):
    """测试创建订单请求构建 - task/buy_helpers.py"""

    def setUp(self):
        from task.buy_helpers import prepare_create_request
        from cptoken import init_ctoken_state
        self.prepare = prepare_create_request
        self.init_state = init_ctoken_state

    def test_basic_request(self):
        tickets_info = {
            "count": 1,
            "screen_id": 456,
            "project_id": 789,
            "sku_id": 123,
            "detail": "测试",
            "buyer_info": [{"name": "测试"}],
            "pay_money": 9000,
        }
        ticket_state = self.init_state()
        url, payload = self.prepare(
            tickets_info, "test_token", False,
            {"data": {"ptoken": "abc="}}, ticket_state,
        )
        self.assertIn("project_id=789", url)
        self.assertIn("ptoken=abc", url)
        self.assertEqual(payload["again"], 1)
        self.assertEqual(payload["token"], "test_token")
        self.assertEqual(payload["newRisk"], True)
        self.assertIn("ctoken", payload)
        self.assertIn("timestamp", payload)

    def test_detail_removed(self):
        tickets_info = {
            "count": 1, "screen_id": 1, "project_id": 1, "sku_id": 1,
            "detail": "应被移除", "buyer_info": [], "pay_money": 0,
        }
        ticket_state = self.init_state()
        _, payload = self.prepare(tickets_info, "token", False, {}, ticket_state)
        self.assertNotIn("detail", payload)

    def test_link_id_in_url(self):
        tickets_info = {
            "count": 1, "screen_id": 1, "project_id": 1, "sku_id": 1,
            "link_id": "link123", "buyer_info": [], "pay_money": 0,
        }
        ticket_state = self.init_state()
        url, _ = self.prepare(tickets_info, "token", False, {}, ticket_state)
        self.assertIn("link_id=link123", url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
