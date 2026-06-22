select t.TYPE,
       listagg(t.id, ',') within group (order by t.id) optypes
from anet.saletypes t
where t.type is not null
  and t.active_df = 1
group by t.type

