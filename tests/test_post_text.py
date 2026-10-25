import textwrap
import unittest
from unittest.mock import MagicMock, patch

import post_new_episode as post


EPISODES = [
    {
        "title": "ラジオはオワコンなのか？ #278",
        "description": textwrap.dedent(
            """
            テレビやネットに押され幾度も衰退を囁かれたラジオが、なぜ荒波をサヴァイブし、そして今や逆襲を果たしているのか？
            その鍵は「電波を売る」から「声で人と繋がる」への事業定義の転換にありました。視覚情報がないからこそ湧く想像力や1対1の親密さ、AI時代だからこそ際立つ人間の肉声の温もり。それらを目的から手段に変えたとき、新しい展開が無限に広がっていったのです。
            時代を勝ち抜くラジオの驚きの生存戦略を解き明かします！
            尚、今回はポッドキャスト「ラジオの人のラジオ」の中で行われた、広島FMの営業・馬場さんとヒサシの対談内容を膨らませたものです。こちらもぜひアクセスお願いします！
            ●ラジオの人のラジオ
            https://open.spotify.com/episode/0Fn7qP9l2v0OtJ5pGro0in?si=O6TlYXOhQIC-FbpT4Nr-_g
            ●ニンゲン広告社への感想やクレームや相談はこちら
            https://ningen-kokokusha-promo-site.vercel.app/
            """
        ).strip(),
        "spotify_url": "https://open.spotify.com/episode/2tJa359uCIixybnowC2j8r",
        "apple_url": "https://podcasts.apple.com/jp/podcast/id1630515609?i=1000797331407",
    },
    {
        "title": "マーケターの脳汁はいつ出るのか？ #277",
        "description": textwrap.dedent(
            """
            代理店と事業会社では、マーケターが大興奮する瞬間はどう違うのか！？
            「仕事の喜び」を感じる時は？相手はどう違うのか。伝達ミスで無意味な1時間のプレゼンをした失敗、若手を登壇させにくい育成のジレンマ、PR施策が思わぬ形でバズった体験をたどりながら、発注者の反応を近くで受け取る代理店と、消費者の声やプロダクト改善に近づける事業会社の距離感を比較。さぁもうそろそろ答えは出たんじゃないか？あなたはどっちに就職したい？
            ●お便りやお悩みはこちらから！
            https://ningen-kokokusha-promo-site.vercel.app/
            """
        ).strip(),
        "spotify_url": "https://open.spotify.com/episode/328lvyUM3SV18fiJFIJsqw",
        "apple_url": "https://podcasts.apple.com/jp/podcast/id1630515609?i=1000796974390",
    },
    {
        "title": "あの大ヒット商品は実は失敗作だった？ 【広告ウルトラクイズ】#276",
        "description": textwrap.dedent(
            """
            帰ってきたぜ！広告トリビアのクイズ大会！
            今回はセレンディピティだ！
            ポストイットやSlackの共通点とは？実はどれも「開発の失敗」や「意外な誤用」から生まれた大ヒット商品です。今回のクイズでは、作り手の意図と受け手の解釈のズレが引き起こした劇的なセレンディピティのドラマが題材です。「身近な名作の意外な正体」を知れば、ヒット商品の見方がガラリと変わるはず！ビジネスの着想にも効く納得のエピソード。これを聞けば、明日には同僚に蘊蓄を語りたくなること間違いなし！
            （全3回ですが、毎週連発ではなく、とびとびで配信いたします）
            """
        ).strip(),
        "spotify_url": "https://open.spotify.com/episode/5bJ4Hi87GwZire4ig6dwNm",
        "apple_url": "https://podcasts.apple.com/jp/podcast/id1630515609?i=1000796211849",
    },
]


class PostTextTests(unittest.TestCase):
    def test_xgd_shortening_when_enabled(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"result":{"xid":"short-id"}}'
        )
        with (
            patch.dict(
                post.os.environ,
                {"ENABLE_XGD_SHORTENING": "1", "XGD_API_KEY": "test-key"},
            ),
            patch.object(post, "xgd_auth_header", return_value="test-auth"),
            patch.object(post, "fetch_response", return_value=response),
        ):
            shortened = post.xgd_shorten_url("https://example.com/long-url")

        self.assertEqual(shortened, "https://x.gd/short-id")

    def test_latest_three_real_episodes_fit_and_print(self):
        for episode in EPISODES:
            with self.subTest(title=episode["title"]):
                text = post.build_post_text(
                    episode["title"],
                    episode["description"],
                    episode["spotify_url"],
                    episode["apple_url"],
                )
                weight = post.weighted_length(text)
                print(f"\n[{episode['title']}]\n{text}\nweighted_length={weight}")
                self.assertLessEqual(weight, post.X_WEIGHT_LIMIT)
                self.assertNotIn("🔥更新🔥", text.splitlines()[0])
                self.assertIn(post.CTA_TEXT, text.splitlines())
                self.assertEqual(text.count(post.HASHTAG), 1)
                if episode["title"].endswith("#276"):
                    self.assertTrue(text.splitlines()[1].startswith(episode["title"]))
                else:
                    self.assertTrue(text.splitlines()[0].startswith(episode["title"]))

    def test_shrinks_in_required_order(self):
        description = f"{'あ' * 200}。{'補' * 200}。"
        title = f"{'題' * 187} #999"

        with patch.object(
            post, "_compose_post_text", wraps=post._compose_post_text
        ) as compose:
            text = post.build_post_text(
                title, description, "https://x.gd/a", "https://x.gd/b"
            )

        calls = [call.args for call in compose.call_args_list]
        self.assertEqual(len(calls), 3)
        self.assertTrue(calls[0][2])
        self.assertTrue(calls[0][5])
        self.assertEqual(calls[1][2], "")
        self.assertTrue(calls[1][5])
        self.assertEqual(calls[2][2], "")
        self.assertFalse(calls[2][5])
        self.assertTrue(all(call.kwargs["title_first"] for call in compose.call_args_list))
        self.assertNotIn(post.HASHTAG, text)
        self.assertNotIn("あ", text)
        self.assertLessEqual(post.weighted_length(text), post.X_WEIGHT_LIMIT)

    def test_long_hook_puts_title_first_and_first_sentence_next(self):
        episode = EPISODES[0]
        text = post.build_post_text(
            episode["title"],
            episode["description"],
            episode["spotify_url"],
            episode["apple_url"],
        )
        lines = text.splitlines()
        first_sentence, _ = post.build_catchy_summary(
            episode["title"], episode["description"]
        )
        self.assertEqual(lines[0], f"{episode['title']} {post.HASHTAG}")
        self.assertEqual(lines[1], first_sentence)

    def test_long_hook_never_puts_hashtag_on_own_line(self):
        episode = EPISODES[0]
        text = post.build_post_text(
            episode["title"],
            episode["description"],
            episode["spotify_url"],
            episode["apple_url"],
        )
        lines = text.splitlines()
        self.assertNotIn(post.HASHTAG, lines)
        self.assertTrue(lines[0].endswith(f" {post.HASHTAG}"))

    def test_short_hook_keeps_hook_before_title(self):
        episode = EPISODES[2]
        text = post.build_post_text(
            episode["title"],
            episode["description"],
            episode["spotify_url"],
            episode["apple_url"],
        )
        lines = text.splitlines()
        hook, supplement = post.build_catchy_summary(
            episode["title"], episode["description"]
        )
        self.assertEqual(lines[0], hook)
        self.assertTrue(lines[1].startswith(episode["title"]))
        self.assertEqual(lines[2], supplement)

    def test_empty_description_uses_title_as_hook(self):
        title = "説明文がない回 #999"
        text = post.build_post_text(
            title, "", "https://x.gd/spotify", "https://x.gd/apple"
        )
        self.assertEqual(text.splitlines()[0], title)

    def test_short_first_sentence_is_joined_and_trailing_comma_becomes_period(self):
        hook, supplement = post.build_catchy_summary(
            "フックテスト #1", "短いです。第二文を連結します。補足です。"
        )
        self.assertEqual(hook, "短いです。第二文を連結します。")
        self.assertEqual(supplement, "補足です。")

        hook, _ = post.build_catchy_summary(
            "フックテスト #1", f"{'あ' * 69}、続きです。"
        )
        self.assertEqual(len(hook), 70)
        self.assertTrue(hook.endswith("。"))

    def test_first_line_never_contains_old_update_marker(self):
        text = post.build_post_text(
            "回帰テスト #1",
            "これは十分な長さがある説明文の第一文です。補足として使う第二文です。",
            "https://x.gd/spotify",
            "https://x.gd/apple",
        )
        self.assertNotIn("🔥更新🔥", text.splitlines()[0])

    def test_cta_matches_exactly(self):
        text = post.build_post_text(
            "CTAテスト #1",
            "これは十分な長さがある説明文の第一文です。補足として使う第二文です。",
            "https://x.gd/spotify",
            "https://x.gd/apple",
        )
        self.assertIn(
            "Apple Podcastでフォローすると、月・水の新着が届きます。",
            text.splitlines(),
        )
        self.assertEqual(post.RELEASE_DAYS_LABEL, "月・水")


if __name__ == "__main__":
    unittest.main()
