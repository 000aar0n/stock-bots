"""htmw_client.py - HANDS. Playwright client skeleton for HTMW.

HANDS does the clicking. Dry run only until Aaron says otherwise.

STATUS: SKELETON. This module is written against the standard HTMW
page flow (login page -> dashboard/portfolio -> order history ->
stock quote page -> trade ticket). The exact selectors are marked
TODO and must be confirmed in a supervised first run before any live
use; they were NOT verified against the live site when this was
written (no credentials were available to the author, by design).

SAFETY:
- Credentials come ONLY from the environment variables HTMW_USER and
  HTMW_PASS. Nothing is hardcoded, nothing is read from files.
- DRY_RUN defaults to True. In dry-run, place_market_order prints the
  intended order and returns without touching the site.
- Flipping DRY_RUN off requires Aaron's explicit approval AND
  credentials supplied for script use. See README.md.

HTMW has no public API. This drives the real website the same way the
scheduled agent sessions do, so it inherits the site's limits
(15 minute delayed quotes, regular hours fills, after-hours orders
fill at the next open).

Requires: pip install playwright  (and `playwright install chromium`)
"""

from __future__ import annotations

import os
import sys

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

DRY_RUN = True  # Aaron must explicitly approve flipping this to False.

BASE_URL = "https://app.howthemarketworks.com"
LOGIN_URL = BASE_URL + "/login"            # TODO: confirm exact path
PORTFOLIO_URL = BASE_URL + "/portfolio"    # TODO: confirm exact path
ORDERS_URL = BASE_URL + "/orders"          # TODO: confirm exact path


class HTMWError(RuntimeError):
    pass


class HTMWClient:
    def __init__(self, dry_run=DRY_RUN):
        self.dry_run = dry_run
        self.user = os.environ.get("HTMW_USER")
        self.password = os.environ.get("HTMW_PASS")
        self._pw = None
        self._browser = None
        self.page = None

    # ------------------------------------------------------------ lifecycle
    def _require_playwright(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise HTMWError(
                "playwright is not installed. Run: pip install playwright "
                "&& playwright install chromium")

    def _require_creds(self):
        if not self.user or not self.password:
            raise HTMWError(
                "HTMW_USER / HTMW_PASS environment variables are not set. "
                "Credentials are never hardcoded or read from files.")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()
        self._browser = self._pw = self.page = None

    # ------------------------------------------------------------ session
    def login(self):
        """Sign in to HTMW. Known gotcha from the agent sessions: the
        username field sometimes comes prefilled with Aaron's school
        email, which the site rejects. Always clear the field and type
        the username (HTMW_USER, i.e. portfoliopilot2) exactly."""
        self._require_playwright()
        self._require_creds()
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self.page = self._browser.new_page()
        self.page.goto(LOGIN_URL)
        # TODO selectors: confirm the real field names/ids on the live
        # login form during the supervised first run.
        user_field = self.page.locator("input[name='username'], "
                                       "input#username").first
        pass_field = self.page.locator("input[name='password'], "
                                       "input#password").first
        user_field.click()
        user_field.press("Control+A")
        user_field.fill(self.user)  # exact username, clears autofill
        pass_field.fill(self.password)
        self.page.locator("button[type='submit'], "
                          "input[type='submit']").first.click()
        self.page.wait_for_load_state("networkidle")
        # TODO: verify success by checking for the account banner
        # ("Welcome, <user>") and raise HTMWError on the site's
        # wrong-username/password message.
        return True

    def _require_login(self):
        if self.page is None:
            raise HTMWError("not logged in - call login() first")

    # ------------------------------------------------------------ reads
    def read_portfolio(self):
        """Return {portfolio_value, cash, loan, buying_power,
        positions: [{symbol, qty, ...}]} parsed from the portfolio /
        account balances pages. TODO: table selectors unconfirmed."""
        self._require_login()
        self.page.goto(PORTFOLIO_URL)
        self.page.wait_for_load_state("networkidle")
        raise NotImplementedError(
            "read_portfolio: page selectors not yet confirmed against "
            "the live site. Confirm in a supervised run, then parse the "
            "balances header and positions table here.")

    def read_order_history(self):
        """Return a list of order dicts {order_id, symbol, side, qty,
        status, price} from the order history page (prices can show "
        "masked as $XXX.xx same-day on HTMW; keep them as None then).
        TODO: table selectors unconfirmed."""
        self._require_login()
        self.page.goto(ORDERS_URL)
        self.page.wait_for_load_state("networkidle")
        raise NotImplementedError(
            "read_order_history: page selectors not yet confirmed "
            "against the live site.")

    # ------------------------------------------------------------ orders
    def place_market_order(self, symbol, side, qty):
        """Place a market order via the stock's trade ticket.

        In DRY_RUN (the default) this only prints the intended order
        and returns a dry-run receipt - it does not even need a login.
        Live submission is intentionally not wired end to end: the
        ticket selectors and the confirm step must be confirmed in a
        supervised run, with Aaron's approval, before DRY_RUN can be
        flipped off.
        """
        side = side.lower()
        if side not in ("buy", "sell", "short", "cover"):
            raise ValueError(f"bad side {side!r}")
        if qty <= 0:
            raise ValueError("qty must be positive")
        order = {"symbol": symbol.upper(), "side": side, "qty": int(qty),
                 "type": "market"}
        if self.dry_run:
            print(f"[HANDS] [DRY RUN] would place: market {side} "
                  f"{qty} x {symbol.upper()} on HTMW (nothing submitted)")
            return {"status": "dry_run", **order}
        self._require_login()
        # TODO live path (supervised confirmation required):
        #   1. goto the symbol quote/trade page
        #   2. open the trade ticket, select side, enter qty, market type
        #   3. preview order, verify symbol/side/qty on the preview
        #   4. submit, then read the order back in order history and
        #      return its real order id and status
        raise NotImplementedError(
            "live order submission is not wired up. Confirm the trade "
            "ticket flow in a supervised run first (see README).")


if __name__ == "__main__":
    if not PLAYWRIGHT_AVAILABLE:
        print("playwright not installed - client skeleton only. "
              "pip install playwright && playwright install chromium",
              file=sys.stderr)
    client = HTMWClient()
    print(client.place_market_order("NVDA", "buy", 1))
