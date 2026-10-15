# personal-agent-skills

QwerTayu の個人用 Claude Code skill を置く、公開の repo。
大学の URL や Chrome のプロファイル名など、身の回りの情報を含む skill は、private の `personal-agent-skills-private` に置く。

## 構成

- skill ごとに `skills/` の下にディレクトリを 1 つ作る（例: `skills/review-in-tab/`）。Claude Code の plugin と同じ `skills/<skill名>/SKILL.md` の形にしておく。
- 各 skill ディレクトリの中身:
  - `SKILL.md`: skill の本体。frontmatter に `name` と `description` を書く。
  - `requirements.md`: その skill の要件と、決まったことの記録。実装の前に書き、変えたら更新する。
  - `scripts/`: SKILL.md から呼ぶスクリプト。
  - `references/`: 必要なときだけ読む詳細な手順書。SKILL.md からリンクする。
- `README.md` に skill の一覧を書く。

## インストール

skill ディレクトリを `~/.claude/skills/` からシンボリックリンクする。

```sh
ln -s "$PWD/skills/<skill名>" ~/.claude/skills/<skill名>
```

## 書き方

- SKILL.md、references、コメントは日本語で書く。コマンド・識別子・ツール名は原文のまま書く。
- SKILL.md は手順の本筋だけにし、長い説明は references に分ける。
- スクリプトは macOS（Apple Silicon、bash 3.2 と system python3）で動くようにする。Python で外部ライブラリが要るときは、PEP 723 の inline metadata を書いて `uv run` で実行する。
- 外部のサービスにお金がかかる手段は使わない。ローカルで無料で動くものを優先する。

## 作業の進め方

- 新しい skill は、ブランチ `feat/<skill名>` を切ってから作る（worktree の切り方は global の CLAUDE.md に従う）。
- ディレクトリを作ったら、まず `requirements.md` を書く。実装はそのあと。
- コミットは頼まれたときだけする。
