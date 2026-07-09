# Bug Report

## 1. Datetime UTC Conversion
- **File:** `app/timeutils.py`
- **Bug:** `parse_input_datetime` stripped timezone information (`replace(tzinfo=None)`) without first converting the time to UTC. This caused times with offsets to be stored with the wrong UTC hour.
- **Fix:** Used `.astimezone(timezone.utc).replace(tzinfo=None)` to properly convert to UTC before stripping the tzinfo.

## 2. Access Token Expiration
- **File:** `app/auth.py`
- **Bug:** `create_access_token` calculated the expiration as `ACCESS_TOKEN_EXPIRE_MINUTES * 60` minutes (which equals 900 minutes) instead of 900 seconds (15 minutes).
- **Fix:** Removed `* 60` so the expiration correctly uses the configured 15 minutes.

## 3. Token Revocation ID
- **File:** `app/auth.py`
- **Bug:** `get_token_payload` checked if `payload.get("sub")` was in `_revoked_tokens`. However, `revoke_access_token` correctly stored the `jti` (JWT ID). This meant logout didn't work for access tokens.
- **Fix:** Changed the check in `get_token_payload` to `payload.get("jti")`.

## 4. Single-use Refresh Tokens
- **File:** `app/routers/auth.py`
- **Bug:** The `/refresh` endpoint did not revoke the presented refresh token, allowing it to be reused indefinitely.
- **Fix:** Added a check against `_revoked_tokens` and added the presented refresh token's `jti` to `_revoked_tokens` during refresh.

## 5. Registration Duplicate Username
- **File:** `app/routers/auth.py`
- **Bug:** `register` returned a 201 response containing the existing user's details if the username already existed in the organization, instead of raising a 409 error.
- **Fix:** Changed to raise `AppError(409, "USERNAME_TAKEN", ...)` when `existing is not None`.

## 6. Reference Code Generation Race Condition
- **File:** `app/services/reference.py`
- **Bug:** `next_reference_code` had a race condition due to a pause (`_format_pause()`) between reading and updating the counter. Concurrent requests could receive the same reference code.
- **Fix:** Added a `threading.Lock()` to synchronize access to the counter.

## 7. Rate Limit Race Condition
- **File:** `app/services/ratelimit.py`
- **Bug:** `record_and_check` had a race condition between reading the bucket, pausing, and writing the updated bucket, allowing the rate limit to be bypassed under concurrent load.
- **Fix:** Added a `threading.Lock()` to synchronize the rate limit check and update.

## 8. Booking Creation & Cancellation Race Conditions
- **File:** `app/routers/bookings.py`
- **Bug:** `create_booking` and `cancel_booking` performed database reads (conflict check, quota check, status check) followed by pauses and then writes. This allowed concurrent requests to bypass conflict, quota, and double-cancel rules.
- **Fix:** Wrapped the critical sections of `create_booking` and `cancel_booking` in a `threading.Lock()`.

## 9. Booking Conflict Logic
- **File:** `app/routers/bookings.py`
- **Bug:** `_has_conflict` checked `b.start_time <= end and start <= b.end_time`, which incorrectly flagged back-to-back bookings (e.g., 10-11 and 11-12) as conflicts.
- **Fix:** Changed the operators to strictly less than (`<`).

## 10. Booking Duration and Grace Window
- **File:** `app/routers/bookings.py`
- **Bug:** `create_booking` allowed a 300-second grace window for `start_time` in the past. It also lacked a check for the minimum duration of 1 hour, allowing negative or zero-length bookings.
- **Fix:** Removed the grace window (`now - timedelta(seconds=300)` -> `now`) and added a `< MIN_DURATION_HOURS` check.

## 11. Booking Pagination
- **File:** `app/routers/bookings.py`
- **Bug:** `list_bookings` used `desc()` instead of `asc()` for sorting, calculated offset incorrectly as `page * limit`, and hardcoded the limit to `10`.
- **Fix:** Changed to `asc()`, fixed offset to `(page - 1) * limit`, and used the `limit` variable in `.limit()`.

## 12. Booking Visibility
- **File:** `app/routers/bookings.py`
- **Bug:** `get_booking` did not check if the requesting user owned the booking or was an admin, allowing members to read other members' bookings.
- **Fix:** Added the authorization check `if user.role != "admin" and booking.user_id != user.id:` to raise a 404.

## 13. Booking Response Field Overwrite
- **File:** `app/routers/bookings.py`
- **Bug:** `get_booking` incorrectly overwrote `response["start_time"]` with `booking.created_at`.
- **Fix:** Removed the line that overwrites `start_time`.

## 14. Cancellation Refund Calculation
- **File:** `app/routers/bookings.py`
- **Bug:** The refund tier logic incorrectly evaluated `notice_hours > 48` (instead of `>= 48`) and lacked a 0% tier for notice under 24 hours. Additionally, floating-point rounding for half-cents did not consistently round up.
- **Fix:** Corrected the thresholds using `timedelta` comparisons, added the 0% tier, and used integer arithmetic `(price * percent + 50) // 100` to properly round half-cents up.

## 15. Cache Invalidation
- **File:** `app/routers/bookings.py`
- **Bug:** `create_booking` did not invalidate the usage report cache, and `cancel_booking` did not invalidate the availability cache, violating the rule that these endpoints reflect the current state immediately.
- **Fix:** Added the missing cache invalidation calls to both endpoints.

## 16. Multi-tenancy Data Leak in Export
- **File:** `app/services/export.py`
- **Bug:** When `include_all` was True and `room_id` was provided, `generate_export` called `fetch_bookings_raw` which did not filter by `org_id`. This allowed an admin to fetch bookings for a room in a different organization.
- **Fix:** Replaced the call to `fetch_bookings_raw` with `_fetch_scoped`, ensuring the `org_id` filter is always applied.

## 17. Room Stats Inconsistency
- **File:** `app/routers/rooms.py` and `app/services/stats.py`
- **Bug:** The `/stats` endpoint relied on an in-memory counter (`services/stats.py`) which could easily lose synchronization with the database, especially on service restart, returning 0 despite existing bookings.
- **Fix:** Rewrote `room_stats` to query the database directly using `func.count` and `func.sum`, ensuring absolute consistency with the booking data.

## 18. Missing Validation for End Time
- **File:** `app/routers/bookings.py`
- **Bug:** The application did not verify that `end_time` is later than `start_time`, allowing invalid bookings with negative or zero duration to proceed through the parsing logic.
- **Fix:** Added a check `if end <= start:` to explicitly raise an `INVALID_BOOKING_WINDOW` error.

## 19. Missing Date Range Validation
- **File:** `app/routers/admin.py`
- **Bug:** The `/usage-report` endpoint validated the date formats but did not verify that the `from` date was earlier than or equal to the `to` date, allowing invalid ranges.
- **Fix:** Added a check `if from_date > to_date:` to explicitly raise an `INVALID_BOOKING_WINDOW` error.

## 20. Missing Swagger UI Authorize Button
- **File:** `app/auth.py`
- **Bug:** The application manually extracted the token from `request.headers` instead of using a FastAPI security dependency, causing the Swagger UI OpenAPI docs to not generate the "Authorize" button.
- **Fix:** Added `HTTPBearer(auto_error=False)` as a dependency to `get_token_payload` to signal to Swagger UI that the endpoints require Bearer authentication.

## 21. Deadlock in Notifications
- **File:** `app/services/notifications.py`
- **Bug:** `notify_created` acquired `_email_lock` then `_audit_lock`, while `notify_cancelled` acquired `_audit_lock` then `_email_lock`. If two concurrent requests triggered these simultaneously, they would deadlock the server forever.
- **Fix:** Reversed the lock acquisition order in `notify_cancelled` so both functions acquire `_email_lock` first, followed by `_audit_lock`.

## 22. Inaccurate Refunds due to Floating-Point Math
- **File:** `app/services/refunds.py` and `app/routers/bookings.py`
- **Bug:** While `bookings.py` correctly calculated the refund amount using integer arithmetic, it incorrectly passed `refund_percent` to `log_refund`. `log_refund` then completely ignored the safe integer calculation and recalculated the refund using floating-point math (`dollars * (percent / 100.0)`), which can result in rounding errors and lost pennies.
- **Fix:** Modified `log_refund` to directly accept `amount_cents` as an integer and updated `bookings.py` to pass the safely pre-calculated `refund_amount_cents`.

## 23. N+1 Query in Usage Report
- **File:** `app/routers/admin.py`
- **Bug:** The `/usage-report` endpoint queried the database for bookings inside a loop over rooms, resulting in an N+1 query performance issue.
- **Fix:** Optimized the query to use `func.count()` and `func.sum()` with a `.group_by(Booking.room_id)`, fetching all aggregated stats in a single efficient database query.

## 24. Missing Content-Disposition Header for CSV Export
- **File:** `app/routers/admin.py`
- **Bug:** The `/export` endpoint returned a `Response` with `media_type="text/csv"` but lacked a `Content-Disposition` header, which prevents browsers from downloading the response as a file (displaying the raw text inline instead).
- **Fix:** Added `headers={"Content-Disposition": "attachment; filename=export.csv"}` to the response to properly trigger a file download prompt.
