{# ---------------------------------------------------------------------------
   Parsers for the deliberately-messy raw layer. See DATA.md for the defect
   catalogue these undo. Every defect is recoverable, so these never lose data.
   --------------------------------------------------------------------------- #}

{# Brazilian money: '187.47' | 'R$ 272,76' | '1.234,56'
   A comma means comma-is-decimal and dots are thousands separators. #}
{% macro parse_money(col) %}
    cast(
        case
            when {{ col }} is null then null
            when position(',' in replace(replace({{ col }}, 'R$', ''), ' ', '')) > 0
                then replace(replace(replace(replace({{ col }}, 'R$', ''), ' ', ''), '.', ''), ',', '.')
            else replace(replace({{ col }}, 'R$', ''), ' ', '')
        end
    as decimal(14,2))
{% endmacro %}

{# Four interleaved timestamp encodings, incl. epoch seconds.
   Epochs were emitted from naive UTC wall time, so `at time zone 'UTC'`
   recovers the original value exactly. #}
{% macro parse_ts(col) %}
    coalesce(
        try_strptime(trim({{ col }}), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim({{ col }}), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim({{ col }}), '%d/%m/%Y %H:%M'),
        try_strptime(trim({{ col }}), '%Y-%m-%d'),
        case
            when regexp_matches(trim({{ col }}), '^[0-9]{9,11}$')
            then cast(to_timestamp(try_cast(trim({{ col }}) as bigint)) at time zone 'UTC' as timestamp)
        end
    )
{% endmacro %}
