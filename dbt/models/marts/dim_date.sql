with spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('1870-01-01' as date)",
        end_date="cast('2031-01-01' as date)"
    ) }}

),

days as (

    select cast(date_day as date) as date_day
    from spine

)

select
    date_day,
    extract(year from date_day)::integer       as year,
    extract(quarter from date_day)::integer    as quarter,
    extract(month from date_day)::integer      as month,
    to_char(date_day, 'FMMonth')               as month_name,
    extract(isoyear from date_day)::integer    as iso_year,
    extract(week from date_day)::integer       as iso_week,
    extract(isodow from date_day)::integer     as day_of_week,
    to_char(date_day, 'FMDay')                 as day_name,
    extract(isodow from date_day) in (6, 7)    as is_weekend
from days
