---
name: review-in-tab
description: セルフレビューや敵対的評価を、herdr の同じワークスペースにある Review タブの claude（他人の PR などは PR 用の worktree の claude）に頼む。「セルフレビューして」「敵対的評価をして」と頼まれたとき、また code-review / security-review を使う前に、まずこの skill を読む。herdr の外や、自分がレビュー役のときは、今のセッションで普通にレビューする。
---

# review-in-tab

レビューは、作業しているセッションとは別の claude に頼む。同じ文脈を持ったままだと、自分の書いたものを甘く見てしまうからだ。
レビュー役は、ふつうは同じワークスペース（= 同じリポジトリ）の `Review` タブで動かし、`review-<ワークスペース ID>`（例: `review-wV`）という名前を付ける。
他人の PR や、今のブランチと違う PR をレビューするときは、PR 用の worktree（ブランチ `review-pr-<PR 番号>`）を作り、そこの claude に頼む。Review タブは依頼したセッションと同じ作業ツリーを見るので、そこで別のブランチを checkout すると、作業中の内容の足元が変わってしまうからだ。

## 1. 自分でレビューするか決める

ワークスペースとタブは、起動したときの環境変数ではなく、今のペインから取る（ペインはほかのタブやワークスペースへ移せるため）。

```sh
echo "$HERDR_ENV"
herdr pane get "$HERDR_PANE_ID"   # "workspace_id" と "tab_id"
herdr tab get <tab_id>            # "label" がタブの名前
```

次のどれかなら、ここで止めて、今のセッションで普通にレビューする（code-review / security-review を頼まれたなら、その skill をそのまま使う）。

- `HERDR_ENV` が `1` でない（herdr の外で動いている）
- 今いるタブの名前が `Review` である
- ListAgents の先頭に出る自分の名前（「This session is …」のあとの、`[…]` の前まで）が `review-<workspace_id>` とちょうど同じ（タブ名が変えられていても、自分がレビュー役だとわかる。`review-in-tab-e1` のように、フォルダ名が `review-` で始まるだけの名前は当たらない）
- 今のブランチ（`git branch --show-current`）が `review-pr-` で始まる（PR 用の worktree のレビュー役である）
- code-review に `--fix` か `--comment` が付いている（ファイルを書き換える、またはユーザーに確かめずに PR に投稿するので、レビュー役には回さない）

2 つ目から 4 つ目は、レビュー役がさらにレビュー役に頼んで終わらなくなるのを防ぐためのものである。

## 2. どこでレビューするか決める

- **ローカルの変更**（作業ツリーやブランチのセルフレビュー）: Review タブで行う。3 へ進む。
- **PR**: PR の HEAD と、今の作業ツリーを比べる。

  ```sh
  gh pr view <PR 番号> --json headRefOid,baseRefName   # PR の HEAD のコミットと、マージ先のブランチ
  git rev-parse HEAD
  git status --porcelain                               # 何も出なければ、まだコミットしていない変更はない
  ```

  - `headRefOid` が今の HEAD とちょうど同じで、まだコミットしていない変更もない（自分の PR を、その作業ブランチでレビューする）: Review タブで行う。3 へ進む。
  - それ以外（他人の PR、今のブランチと違う PR、まだ push していないコミットがある、など）: PR 用の worktree で行う。5 へ進む。GitHub 上の PR と、レビューするコードが食い違わないようにするためだ。
  - PR が今のリポジトリのものでなければ、ユーザーに聞く。

## 3. Review タブとレビュー役を探す

```sh
herdr tab list --workspace <workspace_id>   # "label":"Review" のタブを探す
```

ListAgents で `review-<workspace_id>` を探す。

- **Review タブが 1 つあり、ListAgents にその名前が 1 つある**: レビュー役がそのタブにいるかを確かめてから、6 へ進む。`herdr pane list --workspace <workspace_id>` で、Review タブの `tab_id` を持つペインのどれかの `terminal_title_stripped` が `review-<workspace_id>` とちょうど同じならよい（`--name` で起動した claude は、`✳ review-wV` のように名前をタイトルに出す。`_stripped` は先頭の記号を外したもの）。入っていなければ、レビュー役は別のタブにいるので、ユーザーに伝えて、どうするか聞く。
- **Review タブがない、かつ ListAgents にその名前もない**: 4 へ進む。
- **それ以外**（Review タブが 2 つ以上ある、名前が 2 つ以上ある、タブはあるが名前がない、名前はあるがタブがない）: 作らずに、見つかったものをユーザーに伝えて、どうするか聞く。

## 4. Review タブを作る

タブを作り、dev-layout の `tab` モードで並べて、左のペインで claude を起動する。cwd は今のリポジトリ（worktree ならその worktree）にする。

起動した直後の claude は、まだメッセージを受け取れない。herdr が claude を見つけるまでは `agent_not_found` が返るので、返らなくなるまで試し直す（ふつうは数秒）。

シェル変数は Bash の呼び出しをまたいで残らないので、次のブロックは 1 回の呼び出しでまとめて実行する。

```sh
ws=<workspace_id>
dir=$(git rev-parse --show-toplevel) || { echo "リポジトリの外にいる"; exit 1; }
pane=$(herdr tab create --workspace "$ws" --cwd "$dir" --label Review --no-focus \
  | grep -o '"pane_id": *"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
[ -n "$pane" ] || { echo "タブを作れなかった"; exit 1; }
echo "pane=$pane"
~/dotfiles/herdr/plugins/dev-layout/apply-layout.sh tab "$pane" Review "claude --name review-$ws" \
  || { echo "並べられなかった"; exit 1; }
for i in $(seq 1 30); do
  r=$(herdr agent wait "$pane" --until idle --timeout 30000 2>&1)
  printf '%s' "$r" | grep -q agent_not_found || break
  sleep 1
done
printf '%s\n' "$r"
```

どれかで止まったら、作りかけのタブ（あれば）をユーザーに伝える。勝手に閉じない。

そのあと、ListAgents に `review-<ws>` が出るまで、数回試し直す。

- 時間切れになったとき、または ListAgents に出ないとき: claude が確認の画面（フォルダを信頼するかなど）で止まっていることが多い。`herdr agent read <ペイン ID>`（上のブロックで出した `pane=`）で画面を見る。確認の画面なら、ユーザーに「Review タブで答えてほしい」と伝えて待つ。

できたら 6 へ進む。

## 5. PR 用の worktree を作る

PR の HEAD から、ブランチ `review-pr-<PR 番号>` の worktree を `herdr worktree create` で作る。新しいワークスペースができ、dev-layout が左のペインで claude を起動する。

先に、前のレビューの worktree が残っていないかを見る。`git branch --list 'review-pr-<PR 番号>'` で何か出たら、作らずにユーザーに伝えて、消して作り直すか、そのまま使うかを聞く。そのまま使うときは、その worktree の `git rev-parse HEAD` と `headRefOid` を比べる。違えば前のレビューのときの HEAD のままなので、作り直しを勧める。

worktree は、worktree の中からは作れない（`linked_worktree_source` になる）。元のリポジトリから作る。ここでも、次のブロックは 1 回の呼び出しでまとめて実行する。

```sh
n=<PR 番号>
base=<マージ先のブランチ（2 で取った baseRefName）>
common=$(git rev-parse --path-format=absolute --git-common-dir) || { echo "リポジトリの外にいる"; exit 1; }
root=$(dirname "$common")
git -C "$root" fetch origin "$base" || { echo "マージ先のブランチを取れなかった"; exit 1; }  # origin/<base> を新しくする
git -C "$root" fetch origin "pull/$n/head" || { echo "PR を取れなかった"; exit 1; }
sha=$(git -C "$root" rev-parse FETCH_HEAD)
out=$(herdr worktree create --cwd "$root" --branch "review-pr-$n" --base "$sha" --label "review-pr-$n" --no-focus)
ws=$(printf '%s' "$out" | grep -o '"workspace_id": *"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
pane=$(printf '%s' "$out" | grep -o '"pane_id": *"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
[ -n "$pane" ] || { printf '%s\n' "$out"; echo "worktree を作れなかった"; exit 1; }
echo "ws=$ws pane=$pane"
# 新しいワークスペースは一覧の最後に入るので、元のリポジトリのワークスペースのすぐ下へ動かす（herdr/readme.md の workspace.move）
parent=$(herdr worktree list --cwd "$root" | grep -o '"source_workspace_id": *"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
idx=$(herdr workspace list | grep -o '"workspace_id": *"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' | grep -nx "$parent" | cut -d: -f1)
if [ -n "$idx" ]; then  # grep -n は 1 から数えるので、そのまま「すぐ下」の insert_index になる
  res=$(printf '{"id":"1","method":"workspace.move","params":{"workspace_id":"%s","insert_index":%s}}\n' "$ws" "$idx" \
    | nc -U -w 2 "${HERDR_SOCKET_PATH:-$HOME/.config/herdr/herdr.sock}")
  case "$res" in *'"error"'*|'') echo "並べ替えられなかった: $res" ;; esac
else
  echo "元のワークスペースが見つからないので、並べ替えなかった"
fi
for i in $(seq 1 30); do
  r=$(herdr agent wait "$pane" --until idle --timeout 30000 2>&1)
  printf '%s' "$r" | grep -q agent_not_found || break
  sleep 1
done
printf '%s\n' "$r"
```

dev-layout が起動する claude には `--name` が付かないので、名前はフォルダ名に 16 進 2 桁が付いた `review-pr-<PR 番号>-<2 桁>`（例: `review-pr-1-37`）になる。ListAgents で、この形にちょうど合う名前を探す（`review-pr-1-` は `review-pr-12-…` には当たらない）。出るまで数回試し直す。1 つも出ない、または 2 つ以上あるときは、ユーザーに伝えて止める。時間切れや確認の画面のときは、4 と同じように扱う。

レビューが終わっても、worktree は消さない。ユーザーに頼まれたら、`herdr worktree remove --workspace <ws>` と `git -C <元のリポジトリ> branch -D review-pr-<PR 番号>` で片付ける。

## 6. レビューを頼む

ListAgents で、レビュー役の状態が `idle` でなければ、その状態をユーザーに伝える。

- `busy` などのとき: ほかのレビューの途中である。新しい依頼は、今のレビューが終わるまで処理されない。
- `waiting` のとき: 承認や入力を待って止まっている。Review タブでユーザーが答えるまで、依頼は処理されない。

依頼の種類を決める。

- **ローカル**: 作業ツリーやブランチのセルフレビュー。結果は Review タブに表示するだけで、どこにも投稿しない。
- **PR**: PR のレビュー（PR の番号や URL を渡されたとき、PR をレビューしてと頼まれたとき）。PR へのコメントは外から見える操作で、ユーザーのアカウントで投稿される。そのため、投稿してよいかを必ずユーザーに確かめてから投稿する。

結果は Review タブに表示するだけで、このセッションには返してもらわない。ユーザーは Review タブで結果を読み、このセッションに伝える内容を自分で選ぶ。

SendMessage で、3〜5 で見つけたレビュー役（`review-<ws>` または `review-pr-<PR 番号>-<2 桁>`）に送る。依頼には次を書く。

- **役割**: 「あなたはこの変更のレビュワーです」と書き出す。指摘は、そのまま PR のレビューコメントとして出せる文面で書いてもらう。依頼の経路（この skill で頼まれたこと、タブやセッションのあいだでやり取りしたこと）には触れさせない。変更の中身が herdr などを扱うときは、その説明は普通に書いてよい。
- **種類**: ローカルか PR か。PR なら、その番号か URL。
- **対象**: リポジトリのパス、ブランチ、比べる基点（ふつうは `origin/main`。ローカルの main は古いことがある）、見るべき差分を出すコマンド（例: `git fetch` のあと `git diff origin/main...HEAD`、PR 用の worktree なら `git diff origin/<baseRefName>...HEAD`（5 でマージ先のブランチも取ってある）、リモートがなければ `git diff main...HEAD`、まだコミットしていない変更なら `git diff`、新しいファイルならそのパス）
- **観点**: 頼まれた内容に合わせる
  - セルフレビュー: 正しさ、書き漏れ、周りのコードとの食い違い
  - 敵対的評価: 壊れる入力や状態を積極的に探す。「たぶん大丈夫」で済ませない
  - code-review / security-review: レビュー役にその skill を使ってもらう（引数があればそのまま渡す。`--fix` と `--comment` は 1 で外してある）。結果はその skill の決まりどおりに出してよい。PR に投稿するときは、その結果を下の約束どおりタグ付きのコメントに直してから、「PR のとき」の手順で確かめる
- **作業の背景**: 何のための変更か、気になっている所
- **約束**:
  - 前のレビューの内容は持ち込まず、この依頼だけを見る。
  - PR のとき: 先に `gh api repos/<owner>/<repo>/pulls/<番号>/comments` で、PR に今あるコメントを読む。すでに出ている指摘は、新しいコメントとしてもう一度出さない。
  - ファイルを書き換えない。
  - コメントごとに、場所（ファイルと行）を書く。直してほしい点なら、何が起きるかと直し方も書く。
  - コメントごとに、確からしさ（高・中・低）を書く。実際に動かして確かめたのか、読んで推し量っただけなのかも書く。
  - コメントの先頭に、次のタグを 1 つ付ける。タグは重さを、確からしさはどれだけ確かかを表す。
    - `must:` 直さないとマージできない
    - `should:` 直したほうがよい
    - `imo:` 個人的な意見
    - `nit:` 細かい点
    - `info:` 直さなくてよい。知っておくとよいこと
    - `ask:` 質問。答えがないと判断できない、意図や意味をつかむのに大事なこと
    - `good:` 特に良いと思った点
    - `next:` この PR の範囲の外だが、改善できると気づいたこと
  - PR のとき: 投稿する前に、投稿するコメントを、タグと確からしさを付けてユーザーに見せ、投稿してよいかを確かめる。投稿する本文には、確からしさと依頼の経路を入れない。
  - PR のとき: 投稿する直前に、`gh pr view <番号> --json headRefOid` と、レビューした HEAD（`git rev-parse HEAD`）が同じかを確かめる。違えば（まだ push していないコミットがある、レビューのあいだに push された、など）、行番号がずれるので投稿せずにユーザーに伝える。投稿するときは、レビュー API の `commit_id` にその SHA を渡す。
  - 結果は Review タブに表示するだけで、依頼したセッションには返さない。

送ったら、ユーザーに「Review タブに頼んだ。結果は Review タブに出る」と伝えて、ターンを終える。レビューが終わるのを待たない。

送った時点で失敗が返ったら（名前が見つからない、など）、ユーザーに伝える。あとから配送の通知（`[Cross-session delivery notice]`）で保留や拒否と届いたら、「レビュー役のタブで承認が要る」などとユーザーに伝える。権限モードが送り手と違うと、メッセージは受け手のユーザーの承認待ちになる。通知を待つことはしない。
