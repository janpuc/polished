-- 008_api_tokens.sql: sign-in for the native app (docs/NATIVE.md 2.4 and 3).
--
-- Only new tables; nothing existing is touched, so it is safe on the live database.

-- One row per signed-in device. The token itself is shown once, at the exchange; only its
-- sha256 is stored. A revoked token keeps its row (revoked_at) so "Devices" can say when.
create table api_token (
  id          integer primary key,
  user_sub    text not null,
  user_name   text not null,
  device_name text not null,
  platform    text not null,
  app_version text,
  token_hash  text not null unique,                           -- sha256 hex of the token
  created_at  text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  last_used_at text,                                          -- written at most once a minute
  revoked_at  text
);
create index api_token_user on api_token (user_sub);

-- The one-time code between /auth/app/finish and POST /api/v1/auth/exchange: 60 seconds,
-- single use, bound to the web session's user and to the app's PKCE challenge.
create table app_login_code (
  code_hash   text primary key,                               -- sha256 hex of the code
  user_sub    text not null,
  user_name   text not null,
  challenge   text not null,                                  -- base64url(sha256(verifier))
  device_name text not null,
  expires_at  text not null,
  used_at     text
);
