---
id: forum-sso-loop
title: Community: SSO login loop with Okta
source: forum
---
Posted by devops_dana. After enabling SAML with Okta our users get stuck in a redirect loop on login. It turned out the Okta app had the audience URI set to the ACS URL instead of the Entity ID. Once we changed the audience to the Nimbus Entity ID the loop stopped. Another user, priya_k, reported the same loop when the NameID format was set to unspecified; switching to EmailAddress fixed it for them. A moderator confirmed that clock drift larger than five minutes between the IdP and Nimbus also causes silent SAML failures, so check NTP on self hosted IdPs. Marked as solved. Tip: keep one break glass administrator with a password so you cannot lock yourself out while testing single sign-on.
