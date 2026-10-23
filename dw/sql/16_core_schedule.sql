-- SHIPPING SCHEDULE and the buyer's order status PDF (N-04): current version of each.
CREATE TABLE core.shipping_schedule AS
SELECT s.*, date_diff('day', s.etd_vn, s.rdd) AS rdd_minus_etd
FROM raw.shipping_schedule s JOIN core.current_file f USING (file_id);

CREATE TABLE core.buyer_order_status AS
SELECT b.* FROM raw.buyer_order_status b JOIN core.current_file f USING (file_id);
