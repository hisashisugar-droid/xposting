import textwrap
import unittest
from unittest.mock import MagicMock, patch

import post_new_episode as post


# twitter-text v3 ranges で算出した既知の投稿本文と重み付き文字数。
KNOWN_POST_TEXT = "\n\n".join(
    [
        "優れた広告ほどなぜ心が冷めるのか!?",
        (
            "便利になりすぎた現代、何回も追いかけてくるネット広告や"
            "自動化されたLINEに「私、マーケティングされてる…」と"
            "冷めていませんか？"
        ),
        (
            "Spotify: https://open.spotify.com/episode/"
            "75KcQLL6akJyGKNW7nHsDT / Apple: "
            "https://podcasts.apple.com/jp/podcast/"
            "id1630515609?i=1000799281439"
        ),
        "#ニンゲン広告社",
    ]
)
KNOWN_POST_WEIGHT = 244


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
    def test_fixed_four_element_format(self):
        title = (
            "優れた広告ほどなぜ心が冷めるのか!? "
            "#マーケティング#トレンド #281"
        )
        description = (
            "便利になりすぎた現代、何回も追いかけてくるネット広告や自動化されたLINEに"
            "「私、マーケティングされてる…」と冷めていませんか？"
            "広告と受け手の距離を考えます。"
        )

        self.assertEqual(
            post.post_display_title(title),
            "優れた広告ほどなぜ心が冷めるのか!?",
        )
        spotify_url = "https://open.spotify.com/episode/75KcQLL6akJyGKNW7nHsDT"
        apple_url = (
            "https://podcasts.apple.com/jp/podcast/"
            "id1630515609?i=1000799281439"
        )

        text = post.build_post_text(
            title, description, spotify_url, apple_url
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "優れた広告ほどなぜ心が冷めるのか!?",
                    "広告と受け手の距離を考えます。",
                    f"Spotify: {spotify_url} / Apple: {apple_url}",
                    "",
                    post.HASHTAG,
                ]
            ),
        )
        self.assertEqual(len([line for line in text.splitlines() if line]), 4)
        self.assertEqual(text.splitlines()[3], "")

    def test_dangling_separator_is_removed(self):
        self.assertEqual(
            post.post_display_title(
                "世界最初のビジネス書には何が書かれていた？｜ #ビジネス史 #282"
            ),
            "世界最初のビジネス書には何が書かれていた？",
        )

    def test_question_title_prefers_payoff_sentence(self):
        title = "世界最初のビジネス書には何が書かれていた？｜ #ビジネス史 #282"
        description = (
            "出版不況のなかでも売れ続けるビジネス書。"
            "では、世界で最初に生まれたビジネス書には一体何が書かれていたのでしょう？"
            "メソポタミア文明のクサビ型文字…ではなく、場所は500年前のイタリア。"
            "1494年に出版された『スムマ』という書物で、記されていたのは"
            "なんと「複式簿記」の基礎でした！"
            "単なる帳簿の付け方にとどまらず、世界中の商売人の価値観を"
            "根本から規定した世紀の大発明とは？"
            "その知られざる原点に迫ります！"
        )
        text = post.build_post_text(
            title,
            description,
            "https://open.spotify.com/episode/3PLIlV4VVmZSRV2sQeRfzb",
            "https://podcasts.apple.com/jp/podcast/id1630515609?i=1000799674877",
        )

        self.assertEqual(
            text.splitlines()[0],
            "世界最初のビジネス書には何が書かれていた？",
        )
        self.assertNotIn("｜", text.splitlines()[0])
        self.assertIn("1494年", text.splitlines()[1])
        self.assertIn("スムマ", text.splitlines()[1])
        self.assertEqual(text.splitlines()[-1], post.HASHTAG)
        self.assertEqual(post.weighted_length(text), 216)

    def test_noise_sentences_are_never_picked(self):
        text = post.build_post_text(
            "売れる広告の条件は？ #999",
            "https://example.com/related は関連回です。"
            "●お便りはこちら\n"
            "生活者の視点が3つの実例から見えてきます。",
            "https://x.gd/spotify",
            "https://x.gd/apple",
        )

        self.assertEqual(
            text.splitlines()[1],
            "生活者の視点が3つの実例から見えてきます。",
        )

    def test_known_post_weight_is_244(self):
        self.assertEqual(len(KNOWN_POST_TEXT), 236)
        self.assertEqual(
            post.weighted_length(KNOWN_POST_TEXT), KNOWN_POST_WEIGHT
        )

    def test_weighted_length_character_and_url_rules(self):
        for character in ("…", "①", "℃", "ﾆ"):
            with self.subTest(character=character):
                self.assertEqual(post.weighted_length(character), 2)
        self.assertEqual(post.weighted_length("×"), 1)
        self.assertEqual(
            post.weighted_length("A https://example.com/a-very-long-path\n"),
            26,
        )

    def test_weighted_length_counts_emoji_zwj_sequence_as_two(self):
        self.assertEqual(post.weighted_length("👩‍💻"), 2)
        self.assertEqual(post.weighted_length("👨‍👩‍👧‍👦"), 2)

    def test_weighted_length_normalizes_to_nfc(self):
        self.assertEqual(post.weighted_length("e\u0301"), 1)

    def test_exact_title_sentence_is_skipped(self):
        title = "マーケターは担当ブランドが好きであるべきか？ #279"
        description = (
            "マーケターは担当ブランドが好きであるべきか？"
            "ブランドへの愛着と判断の関係を考えます。"
        )
        hook, _ = post.build_catchy_summary(title, description)
        text = post.build_post_text(
            title, description, "https://x.gd/spotify", "https://x.gd/apple"
        )

        self.assertEqual(hook, "ブランドへの愛着と判断の関係を考えます。")
        self.assertEqual(text.count(post.display_title(title)), 1)

    def test_title_prefix_sentence_is_skipped(self):
        title = "売れる広告の条件 #280"
        description = (
            "売れる広告の条件を実例から考えます。"
            "生活者の視点が重要です。"
        )
        hook, _ = post.build_catchy_summary(title, description)
        text = post.build_post_text(
            title, description, "https://x.gd/spotify", "https://x.gd/apple"
        )

        self.assertEqual(hook, "生活者の視点が重要です。")
        self.assertEqual(text.count(post.display_title(title)), 1)

    def test_raises_when_hook_is_empty(self):
        title = "マーケターは担当ブランドが好きであるべきか？ #279"
        with self.assertRaisesRegex(
            RuntimeError,
            "条件=フック抽出失敗",
        ) as caught:
            post.build_post_text(
                title,
                "マーケターは担当ブランドが好きであるべきか？",
                "https://x.gd/spotify",
                "https://x.gd/apple",
            )

        message = str(caught.exception)
        self.assertIn("タイトル=", message)
        self.assertIn("リンク=", message)
        self.assertIn("タグ=", message)
        self.assertIn("フック用残量", message)

    def test_episode_278_output(self):
        episode = EPISODES[0]
        text = post.build_post_text(
            episode["title"],
            episode["description"],
            episode["spotify_url"],
            episode["apple_url"],
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "ラジオはオワコンなのか？",
                    "その鍵は「電波を売る」から「声で人と繋がる」への事業定義の転換にありました。",
                    "Spotify: https://open.spotify.com/episode/2tJa359uCIixybnowC2j8r / Apple: https://podcasts.apple.com/jp/podcast/id1630515609?i=1000797331407",
                    "",
                    post.HASHTAG,
                ]
            ),
        )

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
                self.assertEqual(text.count(post.HASHTAG), 1)
                self.assertEqual(text.splitlines()[-1], post.HASHTAG)
                shown_title = post.post_display_title(episode["title"])
                lines = text.splitlines()
                self.assertEqual(lines[0], shown_title)
                self.assertEqual(len([line for line in lines if line]), 4)
                self.assertEqual(lines[-2], "")
                self.assertEqual(lines.count(""), 1)

    def test_over_limit_trims_only_hook(self):
        title = f"{'題' * 80} #999"
        hook = f"{'あ' * 200}。"
        text = post.build_post_text(
            title, hook, "https://x.gd/a", "https://x.gd/b"
        )

        lines = text.splitlines()
        self.assertEqual(lines[0], post.post_display_title(title))
        self.assertLess(len(lines[1]), len(hook))
        self.assertEqual(lines[2], "Spotify: https://x.gd/a / Apple: https://x.gd/b")
        self.assertEqual(lines[3], "")
        self.assertEqual(lines[4], post.HASHTAG)
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
        self.assertEqual(lines[0], post.post_display_title(episode["title"]))
        self.assertEqual(lines[1], post._extract_post_hook(
            episode["title"], episode["description"]
        ))

    def test_hashtag_is_always_the_last_line(self):
        episode = EPISODES[0]
        text = post.build_post_text(
            episode["title"],
            episode["description"],
            episode["spotify_url"],
            episode["apple_url"],
        )
        lines = text.splitlines()
        self.assertEqual(lines[-1], post.HASHTAG)
        self.assertEqual(text.count(post.HASHTAG), 1)

    def test_question_title_picks_quoted_payoff(self):
        episode = EPISODES[2]
        text = post.build_post_text(
            episode["title"],
            episode["description"],
            episode["spotify_url"],
            episode["apple_url"],
        )
        lines = text.splitlines()
        self.assertEqual(lines[0], post.post_display_title(episode["title"]))
        self.assertEqual(
            lines[1],
            "実はどれも「開発の失敗」や「意外な誤用」から生まれた大ヒット商品です。",
        )
        self.assertEqual(lines[-1], post.HASHTAG)

    def test_question_title_uses_non_question_hook(self):
        text = post.build_post_text(
            "広告は人を幸せにするのか？ #999",
            "広告に心を動かされたことはありますか？実例を3つ紹介します。",
            "https://x.gd/spotify",
            "https://x.gd/apple",
        )

        self.assertEqual(text.splitlines()[1], "実例を3つ紹介します。")

    def test_question_only_hook_is_flattened(self):
        text = post.build_post_text(
            "広告を見るとなぜ冷めるのか？ #999",
            "便利な広告に、マーケティングされていると冷めていませんか？",
            "https://x.gd/spotify",
            "https://x.gd/apple",
        )

        hook = text.splitlines()[1]
        self.assertEqual(
            hook,
            "マーケティングされていると冷めてしまうことがあります。",
        )
        self.assertFalse(post._is_question_form(hook))

    def test_empty_description_raises(self):
        title = "説明文がない回 #999"
        with self.assertRaisesRegex(RuntimeError, "条件=フック抽出失敗"):
            post.build_post_text(
                title, "", "https://x.gd/spotify", "https://x.gd/apple"
            )

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

    def test_no_cta_line(self):
        text = post.build_post_text(
            "CTAテスト #1",
            "これは十分な長さがある説明文の第一文です。補足として使う第二文です。",
            "https://x.gd/spotify",
            "https://x.gd/apple",
        )
        self.assertNotIn(
            "Apple Podcastでフォローすると、月・水の新着が届きます。",
            text.splitlines(),
        )
        self.assertEqual(text.splitlines()[-1], post.HASHTAG)

    def test_episode_280_does_not_repeat_the_question(self):
        title = "ユーザーは洗濯機で何を洗ってしまった!?【広告ウルトラクイズ】#280"
        description = (
            "ユーザーは洗濯機で服ではなく何を洗っていた!?"
            "かつて中国の農村で多発した謎の故障。"
            "メーカーが調査して判明した衝撃の正体とは？ "
            "メンバーが自信満々にボケ倒す中、実は現代のモノづくりにも通じる大ヒットの金脈が眠っていました。"
        )
        text = post.build_post_text(
            title, description, "https://x.gd/spotify", "https://x.gd/apple"
        )
        elements = [line for line in text.splitlines() if line]

        self.assertEqual(
            sum(line.startswith("ユーザーは洗濯機で") for line in elements), 1
        )
        self.assertEqual(elements[0], post.post_display_title(title))
        self.assertEqual(
            elements[1],
            "かつて中国の農村で多発した謎の故障。",
        )
        self.assertEqual(elements[-1], post.HASHTAG)
        self.assertLessEqual(post.weighted_length(text), post.X_WEIGHT_LIMIT)

    def test_lint_flags_restated_opening(self):
        warnings = post.lint_description(
            "ラジオはオワコンなのか？ #278",
            "テレビやネットに押され幾度も衰退を囁かれたラジオが、"
            "なぜ荒波をサヴァイブし、そして今や逆襲を果たしているのか？"
            "その鍵は事業定義の転換にありました。",
        )

        self.assertTrue(
            any("説明文の1文目がタイトルの言い換え" in warning for warning in warnings)
        )

    def test_lint_flags_notice_opening(self):
        warnings = post.lint_description(
            "マーケターは担当ブランドが好きであるべきか？ #279",
            "マーケターの仮説ラヂオさんとのコラボの最終回です！"
            "表題の問いはブランドへの愛着に関するものです。",
        )

        self.assertTrue(any("説明文の1文目が告知" in warning for warning in warnings))

    def test_lint_flags_banned_words(self):
        warnings = post.lint_description(
            "洗濯機の意外な使われ方 #280",
            "メーカーが調査して判明した衝撃の正体とは？",
        )

        self.assertTrue(any("煽り語" in warning and "衝撃" in warning for warning in warnings))

    def test_lint_is_silent_for_clean_description(self):
        warnings = post.lint_description(
            "売れる広告の条件 #281",
            "生活者の視点から売れる広告の条件を考えます。実例を3つ紹介します。",
        )

        self.assertEqual(warnings, [])

    def test_lint_runs_on_post_path(self):
        episode = {
            "guid": "test-guid",
            "title": "通常投稿のタイトル #999",
            "description": "通常投稿で確認する説明文です。",
            "rss_episode_url": "https://example.com/episode",
            "pub_date": "Fri, 30 Oct 2026 00:00:00 GMT",
        }
        state = {"posted_guids": []}
        with (
            patch.dict(post.os.environ, {"DRY_RUN": "0"}, clear=True),
            patch.object(post, "load_state", return_value=state),
            patch.object(post, "refresh_apple_show_cache", return_value=False),
            patch.object(post, "latest_episode", return_value=episode),
            patch.object(
                post,
                "build_episode_post",
                return_value=(
                    "投稿文",
                    "https://example.com/spotify",
                    "https://example.com/apple",
                ),
            ),
            patch.object(post, "lint_description", return_value=[]) as lint,
            patch.object(post, "post_to_x", return_value={"data": {"id": "1"}}),
            patch.object(post, "save_state"),
            patch("builtins.print"),
        ):
            result = post.main()

        self.assertEqual(result, 0)
        lint.assert_called_once_with(episode["title"], episode["description"])

    def test_hashtag_is_not_dropped_when_over_limit(self):
        title = f"{'題' * 80} #999"
        text = post.build_post_text(
            title,
            f"{'あ' * 200}。",
            "https://x.gd/a",
            "https://x.gd/b",
        )

        self.assertEqual(text.splitlines()[-1], post.HASHTAG)
        self.assertIn(post.post_display_title(title), text)
        self.assertLessEqual(post.weighted_length(text), post.X_WEIGHT_LIMIT)

    def test_raises_when_required_fields_exceed_limit(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "条件=超過",
        ):
            post.build_post_text(
                f"{'題' * 140} #999",
                "短いフックです。",
                "https://x.gd/a",
                "https://x.gd/b",
            )


if __name__ == "__main__":
    unittest.main()
