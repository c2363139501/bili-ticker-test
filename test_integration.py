"""集成测试 - mock网络请求，验证完整链路。"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

os.environ["BTB_SKIP_INITIAL_TIME_SYNC"] = "1"
sys.path.insert(0, '.')


class MockResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data


def make_new_project_response(project_id=1004295, id_bind=2, ticket_count=1):
    """构造新接口 items_detail/info 的mock返回。"""
    tickets = []
    for i in range(ticket_count):
        tickets.append({
            "id": 900000 + i,
            "price": 9000,
            "desc": f"测试票档{i+1}",
            "sale_start": "2026-10-01 09:00:00",
            "sale_flag": {"number": 2},
            "static_limit": {"num": 8, "limit_option": 0, "num_type": 1},
            "type": 1,
            "anonymous_buy": False,
        })
    return {
        "code": 0,
        "success": True,
        "data": {
            "projectId": project_id,
            "projectName": "测试项目",
            "hotProject": False,
            "idBind": id_bind,
            "screenList": [
                {
                    "id": 100000,
                    "name": "测试场次",
                    "start_time": "1787500800",
                    "express_fee": 0,
                    "ticket_list": tickets,
                }
            ],
            "skuVenueInfo": {"name": "测试场馆", "address_detail": "测试地址"},
            "salesDates": [{"date": "2026-10-01"}],
            "endTime": 1787587199,
        },
    }


def make_old_project_response(project_id=1004295, id_bind=1):
    """构造旧接口 getV2 的mock返回。"""
    return {
        "errno": 0,
        "msg": "",
        "data": {
            "id": project_id,
            "name": "测试项目(旧接口)",
            "id_bind": id_bind,
            "buyer_info": "2,1",
            "hotProject": False,
            "screen_list": [
                {
                    "id": 100000,
                    "name": "测试场次",
                    "start_time": 1787500800,
                    "express_fee": 0,
                    "ticket_list": [
                        {
                            "id": 900000,
                            "price": 9000,
                            "desc": "测试票档",
                            "sale_start": "2026-10-01 09:00:00",
                            "sale_flag_number": 2,
                            "static_limit": {"num": 8},
                        }
                    ],
                }
            ],
            "venue_info": {"name": "测试场馆", "address_detail": "测试地址"},
            "sales_dates": [{"date": "2026-10-01"}],
        },
    }


class TestFetchTicketOptionsIntegration(unittest.TestCase):
    """测试 fetch_ticket_options 完整链路 - id_bind从project级下传到ticket级。"""

    def _make_mock_request(self, response_data):
        mock_req = MagicMock()
        mock_req.post.return_value = MockResponse(response_data)
        mock_req.get.return_value = MockResponse({"errno": 0, "data": {"list": []}})
        mock_req.headers = {}
        return mock_req

    def test_new_api_id_bind_2_flows_to_tickets(self):
        """新接口 idBind=2 应下传到所有票档。"""
        from interface.project import _fetch_ticket_options, fetch_project_payload

        resp = make_new_project_response(id_bind=2, ticket_count=3)
        mock_req = self._make_mock_request(resp)

        payload = fetch_project_payload(request=mock_req, project_id=1004295)
        self.assertEqual(payload["id_bind"], 2)

        options = _fetch_ticket_options(
            request=mock_req, project_payload=payload, selected_date=None
        )
        self.assertEqual(len(options), 3)
        for opt in options:
            self.assertEqual(opt["id_bind"], 2)
            self.assertEqual(opt["max_count"], 8)

    def test_new_api_id_bind_1_flows_to_tickets(self):
        """新接口 idBind=1 应下传到所有票档。"""
        from interface.project import _fetch_ticket_options, fetch_project_payload

        resp = make_new_project_response(id_bind=1)
        mock_req = self._make_mock_request(resp)

        payload = fetch_project_payload(request=mock_req, project_id=1004295)
        self.assertEqual(payload["id_bind"], 1)

        options = _fetch_ticket_options(
            request=mock_req, project_payload=payload, selected_date=None
        )
        self.assertEqual(options[0]["id_bind"], 1)

    def test_new_api_missing_id_bind_defaults_1(self):
        """新接口缺少 idBind 字段时默认为1。"""
        from interface.project import _fetch_ticket_options, fetch_project_payload

        resp = make_new_project_response(id_bind=1)
        del resp["data"]["idBind"]
        mock_req = self._make_mock_request(resp)

        payload = fetch_project_payload(request=mock_req, project_id=1004295)
        self.assertEqual(payload["id_bind"], 1)

        options = _fetch_ticket_options(
            request=mock_req, project_payload=payload, selected_date=None
        )
        self.assertEqual(options[0]["id_bind"], 1)

    def test_old_api_fallback_id_bind(self):
        """新接口失败时回退旧接口，id_bind应正确读取。"""
        from interface.project import _fetch_ticket_options, fetch_project_payload

        old_resp = make_old_project_response(id_bind=2)
        mock_req = MagicMock()
        # 新接口失败
        mock_req.post.side_effect = Exception("new API failed")
        # 旧接口成功
        mock_req.get.return_value = MockResponse(old_resp)
        mock_req.headers = {}

        payload = fetch_project_payload(request=mock_req, project_id=1004295)
        self.assertEqual(payload["id_bind"], 2)
        self.assertEqual(payload.get("buyer_info"), "2,1")

        options = _fetch_ticket_options(
            request=mock_req, project_payload=payload, selected_date=None
        )
        self.assertEqual(options[0]["id_bind"], 2)

    def test_ticket_option_has_all_required_fields(self):
        """票档选项应包含所有必要字段。"""
        from interface.project import _fetch_ticket_options, fetch_project_payload

        resp = make_new_project_response(id_bind=2)
        mock_req = self._make_mock_request(resp)

        payload = fetch_project_payload(request=mock_req, project_id=1004295)
        options = _fetch_ticket_options(
            request=mock_req, project_payload=payload, selected_date=None
        )

        opt = options[0]
        required_fields = [
            "id", "price", "desc", "screen", "screen_id",
            "project_id", "sale_status", "id_bind", "max_count", "display",
        ]
        for field in required_fields:
            self.assertIn(field, opt, f"缺少字段: {field}")


class TestFetchPurchaseContextIntegration(unittest.TestCase):
    """测试 fetch_purchase_context 完整链路。"""

    def test_purchase_context_contains_ticket_options_with_id_bind(self):
        """购票上下文中的票档应包含id_bind。"""
        from interface.project import fetch_purchase_context

        resp = make_new_project_response(id_bind=2)
        mock_req = MagicMock()
        mock_req.post.return_value = MockResponse(resp)
        mock_req.get.return_value = MockResponse({"errno": 0, "data": {"list": [], "addr_list": []}})
        mock_req.headers = {}
        mock_req.get_request_name.return_value = "test_user"
        mock_req.cookieManager.get_config_value.return_value = ""
        mock_req.cookieManager.get_cookies.return_value = []

        with patch("interface.project._make_request", return_value=mock_req):
            context = fetch_purchase_context(1004295)

        self.assertEqual(context["project_id"], 1004295)
        self.assertIn("ticket_options", context)
        self.assertGreater(len(context["ticket_options"]), 0)
        self.assertEqual(context["ticket_options"][0]["id_bind"], 2)
        self.assertIn("buyers", context)
        self.assertIn("addresses", context)


class TestConfigGenerationIdBindFlow(unittest.TestCase):
    """测试配置生成流程中id_bind的传递 - mock所有外部依赖。"""

    def _make_mock_context(self, id_bind=2):
        return {
            "project_id": 1004295,
            "project_name": "测试项目",
            "project_url": "https://show.bilibili.com/platform/detail.html?id=1004295",
            "username": "test_user",
            "phone": "13800138000",
            "is_hot_project": False,
            "has_eticket": True,
            "sales_dates": ["2026-10-01"],
            "selected_date": None,
            "venue": {"name": "测试场馆", "address_detail": "测试地址"},
            "ticket_options": [
                {
                    "id": 900000,
                    "price": 9000,
                    "desc": "测试票档",
                    "screen": "测试场次",
                    "screen_id": 100000,
                    "project_id": 1004295,
                    "sale_status": "预售",
                    "id_bind": id_bind,
                    "max_count": 8,
                    "sale_start": "2026-10-01 09:00:00",
                    "display": "测试场次 - 测试票档 - ￥90.0 - 预售",
                }
            ],
            "buyers": [
                {"name": "张三", "personal_id": "110101199001011234", "id": 1},
                {"name": "李四", "personal_id": "110101199002022345", "id": 2},
                {"name": "王五", "personal_id": "110101199003033456", "id": 3},
            ],
            "addresses": [],
            "cookies": [],
        }

    def _run_config_gen(self, id_bind, count, buyers_selected, *, buyer_select_calls=None):
        """通用的配置生成测试运行器。"""
        from app_cmd.config_generator import generate_ticket_config_interactive

        context = self._make_mock_context(id_bind=id_bind)
        saved_config = {}

        def fake_open(filepath, mode="r", **kwargs):
            m = MagicMock()
            m.__enter__ = MagicMock(return_value=m)
            m.__exit__ = MagicMock(return_value=False)
            def fake_dump(data, f, **kw):
                saved_config.update(data)
            m.write = MagicMock()
            # 用side_effect捕获json.dump
            return m

        with patch("app_cmd.config_generator._select_save_location", return_value="/tmp/test"), \
             patch("app_cmd.config_generator._resolve_cookies", return_value=([{"name": "SESSDATA", "value": "test"}], "test_user", "13800138000")), \
             patch("interface.project.fetch_purchase_context", return_value=context), \
             patch("app_cmd.config_generator.questionary") as mock_q, \
             patch("builtins.open", side_effect=fake_open), \
             patch("os.path.exists", return_value=False), \
             patch("json.dump", side_effect=lambda data, f, **kw: saved_config.update(data)):

            # questionary.text: 项目ID -> 数量 -> 手机号
            mock_q.text.return_value.ask.side_effect = [
                "1004295",  # 项目ID
                str(count),  # 购买数量
                "13800138000",  # 手机号(has_eticket=True时可能不需要)
            ]
            # questionary.select: 票档选择 -> (id_bind=1时)购票人单选
            select_returns = [context["ticket_options"][0]]
            if id_bind == 1:
                select_returns.append(context["buyers"][0])
            mock_q.select.return_value.ask.side_effect = select_returns
            # questionary.checkbox: (id_bind=2时)购票人多选
            if buyer_select_calls is not None:
                mock_q.checkbox.return_value.ask.side_effect = buyer_select_calls
            else:
                mock_q.checkbox.return_value.ask.return_value = buyers_selected
            # questionary.confirm: 确认保存
            mock_q.confirm.return_value.ask.return_value = True
            # questionary.path: 保存位置(如果用到)
            mock_q.path.return_value.ask.return_value = "/tmp/test"

            result = generate_ticket_config_interactive()

        return result, saved_config, mock_q

    def test_id_bind_2_requires_exact_buyer_count(self):
        """id_bind=2时，购票人数量必须等于输入数量。"""
        context = self._make_mock_context(id_bind=2)
        result, saved, mock_q = self._run_config_gen(
            id_bind=2, count=2,
            buyers_selected=[context["buyers"][0], context["buyers"][1]],
        )
        self.assertIsNotNone(result)
        self.assertEqual(saved["id_bind"], 2)
        self.assertEqual(saved["count"], 2)
        self.assertEqual(len(saved["buyer_info"]), 2)

    def test_id_bind_1_allows_single_buyer_with_multiple_count(self):
        """id_bind=1时，只选1个购票人，可以买多张。"""
        result, saved, mock_q = self._run_config_gen(
            id_bind=1, count=5, buyers_selected=None,
        )
        self.assertIsNotNone(result)
        self.assertEqual(saved["id_bind"], 1)
        self.assertEqual(saved["count"], 5)
        self.assertEqual(len(saved["buyer_info"]), 1)

    def test_id_bind_2_wrong_buyer_count_retries(self):
        """id_bind=2时，购票人数量不对会提示重选。"""
        context = self._make_mock_context(id_bind=2)
        result, saved, mock_q = self._run_config_gen(
            id_bind=2, count=2, buyers_selected=None,
            buyer_select_calls=[
                [context["buyers"][0]],  # 只选1个，不对
                [context["buyers"][0], context["buyers"][1]],  # 选2个，对
            ],
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(saved["buyer_info"]), 2)
        # checkbox应该被调用了2次
        self.assertEqual(mock_q.checkbox.return_value.ask.call_count, 2)


class TestBuyStreamParameterConstruction(unittest.TestCase):
    """测试buy_stream参数构建 - 验证tickets_info中id_bind不影响下单参数。"""

    def test_tickets_info_with_id_bind_1_single_buyer(self):
        """id_bind=1，1个购票人买多张，buyer_info只有1人。"""
        tickets_info = {
            "project_id": 1004295,
            "screen_id": 100000,
            "sku_id": 900000,
            "count": 5,
            "id_bind": 1,
            "buyer_info": [{"name": "张三", "personal_id": "110101199001011234"}],
            "pay_money": 45000,
            "detail": "测试项目",
        }
        # 模拟buy.py中的处理
        tickets_info["_prepare_buyer_info"] = tickets_info["buyer_info"].copy()
        tickets_info["buyer_info"] = json.dumps(tickets_info["buyer_info"])

        from task.buy_helpers import build_token_payload
        payload = build_token_payload(tickets_info)

        self.assertEqual(payload["count"], 5)
        # buyer_info应该是原始列表，只有1人
        self.assertEqual(len(payload["buyer_info"]), 1)

    def test_tickets_info_with_id_bind_2_multiple_buyers(self):
        """id_bind=2，每人1张，buyer_info人数=count。"""
        buyers = [
            {"name": "张三", "personal_id": "110101199001011234"},
            {"name": "李四", "personal_id": "110101199002022345"},
        ]
        tickets_info = {
            "project_id": 1004295,
            "screen_id": 100000,
            "sku_id": 900000,
            "count": 2,
            "id_bind": 2,
            "buyer_info": buyers,
            "pay_money": 18000,
            "detail": "测试项目",
        }
        tickets_info["_prepare_buyer_info"] = tickets_info["buyer_info"].copy()
        tickets_info["buyer_info"] = json.dumps(tickets_info["buyer_info"])

        from task.buy_helpers import build_token_payload
        payload = build_token_payload(tickets_info)

        self.assertEqual(payload["count"], 2)
        self.assertEqual(len(payload["buyer_info"]), 2)


class TestEdgeCases(unittest.TestCase):
    """边界/异常测试。"""

    def test_parse_sale_start_time_unsupported_format_raises(self):
        """纯Unix时间戳不支持，应抛ValueError(设计如此)。"""
        from task.buy_helpers import parse_sale_start_time
        with self.assertRaises(ValueError):
            parse_sale_start_time("1787500800")

    def test_build_ticket_option_missing_static_limit(self):
        """缺少static_limit时max_count兜底为8。"""
        from interface.project import _build_ticket_option
        ticket = {"id": 1, "price": 9000, "desc": "test", "sale_flag_number": 2}
        screen = {"id": 1, "name": "test", "express_fee": 0, "project_id": 1}
        option = _build_ticket_option(screen=screen, ticket=ticket, hot_project=False, has_eticket=True, id_bind=2)
        self.assertEqual(option["max_count"], 8)
        self.assertEqual(option["id_bind"], 2)

    def test_build_ticket_option_zero_price(self):
        """0元票档。"""
        from interface.project import _build_ticket_option
        ticket = {"id": 1, "price": 0, "desc": "免费票", "sale_flag_number": 2, "static_limit": {"num": 2}}
        screen = {"id": 1, "name": "test", "express_fee": 0, "project_id": 1}
        option = _build_ticket_option(screen=screen, ticket=ticket, hot_project=False, has_eticket=True)
        self.assertEqual(option["price"], 0)
        self.assertEqual(option["max_count"], 2)

    def test_extract_project_id_from_mall_url(self):
        """mall.bilibili.com链接应能提取项目ID。"""
        from interface.common import _extract_project_id
        result = _extract_project_id("https://mall.bilibili.com/neul-next/ticket-renovation/detail.html?id=1004295")
        self.assertEqual(result, 1004295)

    def test_format_countdown_large_value(self):
        """超大倒计时值。"""
        from task.buy_helpers import format_countdown
        result = format_countdown(999999999)
        self.assertIn("天", result)

    def test_error_codes_all_known(self):
        """所有定义的错误码应能获取消息。"""
        from util.ErrorCodes import ErrorCodes
        codes = [100003, 100009, 100010, 100034, 100048, 100051, 100079, 100081, 100083, 100085, 100086, 100087, 100088, 100089, 100090, 100091, 100092, 100093, 100094, 100095, 100096, 100097, 100098, 100099, 100100, 100101, 100102, 100103, 100104, 100105, 100106, 100107, 100108, 100109, 100110, 100111, 100112, 100113, 100114, 100115, 100116, 100117, 100118, 100119, 100120, 100121, 100122, 100123, 100124, 100125, 100126, 100127, 100128, 100129, 100130, 100131, 100132, 100133, 100134, 100135, 100136, 100137, 100138, 100139, 100140, 100141, 100142, 100143, 100144, 100145, 100146, 100147, 100148, 100149, 100150, 100151, 100152, 100153, 100154, 100155, 100156, 100157, 100158, 100159, 100160, 100161, 100162, 100163, 100164, 100165, 100166, 100167, 100168, 100169, 100170, 100171, 100172, 100173, 100174, 100175, 100176, 100177, 100178, 100179, 100180, 100181, 100182, 100183, 100184, 100185, 100186, 100187, 100188, 100189, 100190, 100191, 100192, 100193, 100194, 100195, 100196, 100197, 100198, 100199, 100200]
        # 不逐个断言，只确保不抛异常
        for code in codes:
            try:
                ErrorCodes.get_message(code)
            except Exception as e:
                self.fail(f"错误码{code}获取消息失败: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
