# config.json と story.json の項目

例は `assets/example/config.json` と `assets/example/story.json`（架空の 2 人）。

## talks/<slug>/config.json

| 項目 | 意味 |
|---|---|
| `slug` | ディレクトリ名と同じ。スクリプトの引数に使う |
| `mode` | `"pair"`（1 対 1）か `"group"`（グループ）。ユーザーに選んでもらう。`parse_line.py` が見出しから見当をつける |
| `title` | ページに出すトーク名（スライドの左上など）。txt のトーク名には人の名前が入るので、そのまま使わない |
| `me` | 本人の、txt の送り手の欄での表示名。1 対 1 は `parse_line.py` が見当をつける。グループは送り手の一覧から選んでもらう |
| `members` | `{txt の表示名: 呼び名}`。ページに出す名前は呼び名だけ。本人も含め、範囲の中で書いた全員の呼び名をユーザーに聞いて書く（1 人でも足りないと止まり、足りない表示名を出す） |
| `sender_aliases` | `{別の表示名: txt の表示名}`。途中で表示名が変わった人や、退会して `Unknown` などになった人を同じ人にまとめる |
| `since` / `until` | 集計する範囲（`"2026-04-01"` の形。どちらも含む。省くと全期間）。直近 1 年の `since` は `parse_line.py` が出す |
| `periods` | 時期の区切り。`[キー, 表示名, [月, ...]]` の配列。月は `4` か `"2026-04"`（年をまたぐときは年月で書く）。範囲のすべての月をどこかに入れる（入らない月があると止まる）。1 つの時期に 50 件以上入るように決め、少ないトークは 2〜3 つにする |
| `gap_hours` | 何時間あいたら別の会話とみなすか（既定 3） |
| `n_topics` / `show_topics` | NMF のトピック数と、トピックの節を出すか。メッセージが数百件ないと寄せ集めになるので、そのときは `show_topics: false`（計算もしない） |
| `compounds` | Sudachi が切ってしまう固有名詞。先に取り出して 1 語として数える |
| `aliases` | 語の表記ゆれをそろえる（例: `"github": "GitHub"`）。`compounds` で取り出した語にもかかる |
| `names` | 語の集計から外す人名。語と完全に一致したときだけ外すので、短い呼び名（「やま」）も入れてよい。メンバーの表示名・その一部・呼び名と、`nicknames` に書いた名前は自動で外れる |
| `nicknames` | 引用の中で置き換える名前。`{名前: 表示する文字列}` で書き、表示は**1 つずつユーザーに聞いて決める**（伏せたいと言われたら「〇〇」、そのままでよければ同じ文字列）。リストで書いたものは「〇〇」になる。3 文字以上の名前は文字列の一部として置き換える。2 文字以下の名前は、普通の語を壊さないよう、敬称（さん・くんなど）が続くときと、Sudachi で 1 語に切れてすぐあとが助詞・記号・文の終わりのときだけ置き換える |
| `extra_stopwords` | 数えても意味のない語（集計結果を見て足す。例: 「ちなみ」は「ちなみに」の切れ端） |
| `expressions` | そのトークの口ぐせ（言い回し）の正規表現。`{"表示名": "正規表現"}`。基本の言い回し（w、草、笑、ぴえん、やばい、えぐい、おもろい、好き、かわいい）に足される |
| `symbols` | 記号の正規表現。`{"表示名": "正規表現"}`。基本の記号（！、？、…、〜、ーー）に足される。記号は言い回しの上位を占めてしまうので、別に数える |
| `period_quote_words` | `{時期のキー: [語, ...]}`。第 n 章の吹き出しの候補に、その語を含むメッセージを優先して入れる（例: `{"p2": ["カレー"]}`） |
| `greetings` | あいさつの正規表現。`{"表示名": "正規表現"}`。省くと「おはよう」と「おやすみ」。グループを使うときは `(?:...)` にする |

`names` と `nicknames` の候補は `scripts/find_names.py` で洗い出す。

txt の表示名は、`members` と `sender_aliases` に書いておけば、引用の中では呼び名に置き換わる。表示名を空白やかっこで区切った一部（「山田 花子（はな）」の「花子」「はな」）も置き換わる。数字だけの部分と 1 文字の部分は置き換えない。

## talks/<slug>/story.json

手で書く文。数字はデータで確かめてから書く。`page_title`・`title`・`lede`・`what_heading`・`periods` と、`wrapped` の `page_title`・`intro_title` は必須。ほかは省くと、数字から見出しや文を作る。

`build.py` は、それぞれのページが使う項目だけを HTML に埋め込む（読み物は `REPORT_KEYS`、スライドは `WRAPPED_KEYS`。`wrapped` の下は `SLIDE_KEYS`、`periods.<キー>` の下は `PERIOD_KEYS`、`wrapped.awards.<呼び名>` の下は `AWARD_KEYS`）。下の表にない項目（メモなど）は、どの階層に書いても HTML には入らない。テンプレートで story の項目を新しく使うときは、`build.py` のこれらも直す。

### 読み物（report.html）

| 項目 | 出る場所 |
|---|---|
| `page_title` | 読み物のタブ名 |
| `title` / `lede` | 表紙 |
| `facts_heading` / `facts_note` | 「ざっくり数字」の見出しと、「いちばん話した日は◯月◯日の◯件。」に続く一文 |
| `when_heading` / `when_body` | 「いつ話しているか」 |
| `what_heading` | 「何を話しているか」の見出し。スライドの時期の見出しにも使う |
| `periods.<キー>.title` / `.body` | 時期ごとのキャッチコピーと説明 |
| `topics` / `topics_note` | `{代表語: 仮の名前}`。代表語はそのトピックの上位 5 語に入っている語（番号は語彙を変えると入れ替わるので使わない） |
| `words_heading` / `words_body` | 口ぐせ（全員分） |
| `people_words_heading` | その人らしい言葉 |
| `habits_heading` | くせ（言い回しと記号の表） |
| `talks_heading` / `talks_body` / `longest_talk_body` | 会話のまとまりと、いちばん長く続いた会話 |
| `speed_heading` / `speed_body` | 反応の速さ |
| `calls_heading` / `calls_body` | 通話（通話がなければ章ごと出ない） |
| `rhythm_heading` / `rhythm_body` | 沈黙と連続 |
| `greetings_heading` | あいさつ（あいさつがなければ出ない） |
| `polite_heading` / `polite_body` | です・ます調の移り変わり |
| `follows_heading` | だれのあとにだれ（グループだけ） |
| `highlights_heading` | 名場面 |
| `show_longest_text` | `false` にすると「いちばん長いメッセージ」を出さない（貼り付けた長文が来たときなど） |
| `next` | 「このあと」の箇条書き |

### スライド（wrapped）

| 項目 | 出る場所 |
|---|---|
| `page_title` / `intro_title` | タブ名と表紙（`\n` で改行） |
| `messages_kicker` | メッセージ数 |
| `share_heading` / `messages_body` | だれが何 % を占めていたか |
| `periods_kicker` | 「ふりかえると」のスライドの小見出し |
| `best_day_body` / `best_day_quote` | いちばん話した日。`best_day_quote` は `highlights.best_day` の何番目から 3 件を吹き出しで出すか（`null` なら出さない） |
| `top_word_body` | いちばん使った言葉の補足 |
| `hour_heading` / `hour_body` | よく話す時間（24 時間の時計） |
| `talks_heading` / `talks_body` | 会話を始めるのは |
| `speed_heading` / `speed_body` | 即レス王（相手が書いてから 1 分以内に返した割合） |
| `habits_heading` / `habits_keys` / `habits_body` | 口ぐせ。`habits_keys` に言い回しの表示名を書くと、人ごとにその中からいちばん割合の高いものを出す（省くと全部から） |
| `battle_heading` / `battle_body` | 対決（1 対 1 だけ）。問いと数字は集計結果から自動で作る |
| `awards_heading` / `awards` | 表彰式。`awards` は `{呼び名: {title, body, emoji}}` で、`recap.json` の `awards`（自動の候補）を上書きする |
| `first_heading` | はじまり |
| `chapter_quotes` | 第 n 章の吹き出し。`{時期のキー: [番号, ...]}`。番号は `recap.json` の `highlights.periods.<キー>` の何番目か（省くと最初の 3 件）。選ばなかった候補は HTML に埋め込まない |
| `longest_talk_heading` / `longest_talk_body` | いちばん長く続いた会話（読み物の `longest_talk_body` とは別） |
| `rhythm_body` / `streak_quotes` | 毎日話した最長。`rhythm_body` は「〇〇の話をしていた」の見出しを上書きする。`streak_quotes` は `recap.json` の `rhythm.streak.quotes`（その期間の特徴語を含む候補、最大 8 件）の何番目を吹き出しで出すか（省くと最初の 3 件）。選ばなかった候補は HTML に埋め込まない |
| `overall_heading` | 期間の章のあと、全期間のまとめに移る区切り（省くと「全期間をまとめてみた」） |
| `card_heading` / `card_body` | まとめカード（最後のスライド） |

