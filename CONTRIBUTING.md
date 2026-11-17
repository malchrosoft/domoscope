# Contributing

Code, bug reports and ideas are welcome — with one condition below.

## Inbound license grant (required)

By submitting a pull request, patch, or any other contribution to this repository, you agree that:

1. you wrote the contribution, or you have the right to submit it;
2. you grant Aymeric MALCHROWICZ a perpetual, worldwide, non-exclusive, royalty-free,
   irrevocable license to use, reproduce, modify, distribute, sublicense and **relicense**
   your contribution under any terms, including a paid commercial license;
3. you grant the same license for any patent claims you can license that your contribution
   necessarily infringes;
4. the contribution is provided "as is", without warranty of any kind.

You keep the copyright on your contribution. This grant is what allows the project to be
dual-licensed; without it, a single contribution would block every future commercial license.

If you cannot accept these terms, open an issue instead of a pull request. Ideas and bug
reports are not covered by this grant.

## Sign-off

Certify each commit with the Developer Certificate of Origin 1.1:

```powershell
git commit -s -m "your message"
```

This adds `Signed-off-by: Your Name <you@example.com>` to the commit message.

## Before submitting

```powershell
uv run ruff check .
uv run pytest
```

Keep the diff focused: one topic per pull request.
