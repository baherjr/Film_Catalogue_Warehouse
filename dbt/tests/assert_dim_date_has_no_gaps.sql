-- 1870-01-01 to 2030-12-31 inclusive is 58,804 days.
-- With date_day unique, the right count means no day is missing.
select count(*) as row_count
from {{ ref('dim_date') }}
having count(*) <> 58804
