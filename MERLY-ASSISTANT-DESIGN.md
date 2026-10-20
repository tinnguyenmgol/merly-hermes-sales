# Merly-branded assistant

Official wordmark, unchanged PNG, sourced from the current storefront logo:
https://file.hstatic.net/1000040357/file/logo-merly-giay-big-size_cad17027eb9745bb931b1aed4fd0c852.png

Logo SHA256: 705add6121d3e6017423fc7864f24f457b1c702247acafcc1d1b24e4910cd327

Replaces generic dark chat icon/floating tooltip with104x64 branded button:
original Merly wordmark + persistent Trợ lý AI caption. Warm taupe/ivory palette
uses original logo color RGB156/134/121. Brand header and static greeting identify
Trợ lý Merly, explicitly AI, not a human agent or a claimed online availability.
No mascot alteration or low-resolution favicon enlargement. Logo served locally
(no ongoing CDN dependency), route GET-only, CSP img-src self only. Keyboard focus
retained without decorative double-circle rings; no hover tooltip on touch.

Same lazy iframe/session/CSRF/rate caps, no checkbox, short notice, no hidden
consent assertion, no extra backend or paid greeting/model calls. No DNS/theme/
key changes. Header/main styles consolidated rather than stacked overrides.

Verification:296 unit/integration tests, Chromium desktop320/390/1440, touch,
logo decoding626px wide, correct source image path, panel bounds, duplicate-tag
singleton, open/close/Escape and message-only request checks. Inventory synthetic;
no live deployment or model call. design-preview/*.png are ACTUAL Chromium renders
of this code on a test page (not screenshots of deployed Haravan/storefront).

Owner can review images before merging design/merly-branded-assistant and deploying
existing app. Refresh storefront after deployment. No change to main by agent.
