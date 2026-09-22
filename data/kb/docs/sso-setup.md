---
id: sso-setup
title: SSO Setup with SAML
source: docs
---
Nimbus Cloud supports SAML 2.0 single sign-on on the Pro and Enterprise plans. To set up SSO, open Settings, choose Security, then Single Sign-On and click Configure SAML. Copy the Nimbus ACS URL and Entity ID into your identity provider, such as Okta or Azure AD. Then upload the IdP metadata XML or paste the metadata URL back into Nimbus. Map the email attribute to the NameID field so users are matched by email address. Before enforcing SSO, test with one administrator account in a private window. Once enforced, password logins are disabled for all members except the workspace owner, who keeps a recovery password. Just-in-time provisioning creates accounts on first login and assigns the default member role. If users see error E110 during login, the certificate in your IdP metadata has probably expired; upload fresh metadata and retry. SCIM provisioning is available on Enterprise only and syncs deactivations within five minutes.
