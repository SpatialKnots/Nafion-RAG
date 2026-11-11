# Canonical decision-map reader diagnostic

After20 rewrite attempts closed, original freeze-plans stopped because canonical
JSON serialization sorts map keys, whereas its reader compared insertion order
to Satoh-first case order. No translation/decision content changed. Original
freeze/runner/input manifest remain immutable. Initial prepare-all stopped at
Satoh01 before retrieval because no plan freeze existed; failure logs preserved.

A separate reader adapter consumes the exact decision key set in frozen case
order. It freezes its own source hash with all original rewrite manifests/results/
plans and decision file, then starts fresh read-only preparation processes with
separate v02 logs. It does not modify the frozen experimental algorithm, prompt,
rewrites or original decisions and does not resend any model request. A focused
regression verifies sorted-map handling/order and unchanged original plan hashes.
