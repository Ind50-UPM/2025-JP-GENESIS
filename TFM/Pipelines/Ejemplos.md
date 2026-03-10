### E1: Bases de datos disponibles
El usuario pregunta cuáles bases de datos hay disponibles

Usuario: bases de datos disponibles

Respuesta: 
📊 **Bases de datos disponibles:**

• **postgres**: Base de datos principal del sistema PostgreSQL
• **trombofilia**: Datos relacionados con estudios de trombofilia
• **1245**: Base de datos del proyecto 1245
• **ncorrea**: Base de datos principal de ncorrea (por defecto)
• **2207**: Base de datos del proyecto 2207
• **autosurveillance**: Sistema de auto-vigilancia
• **deepquality**: Sistema de control de calidad
• **enel**: Datos de Enel
• **enel_guillena**: Datos específicos de Enel Guillena
• **enel_lleida**: Datos específicos de Enel Lleida
• **jom**: Base de datos JOM
• **mapvision**: Datos de MapVision
• **oproject-bin**
• **template0**
• **template1**

💡 **Base de datos por defecto:** ncorrea

### E2: Consulta sobre una base de datos específica
Para este caso el usuario consulta sobre la BD de trombofilia datos como las tablas disponibles, los nombres de las columnas de una tabla determinada y 10 registros de la misma tabla

Usuario: ve a trombofilia

Respuesta:
✅ **Contexto cambiado a: trombofilia**

📋 Datos relacionados con estudios de trombofilia

Ahora todas tus consultas usarán la base **trombofilia**.

💡 Ejemplos:
• 'muéstrame 10 registros de pacientes'
• 'columnas de tratamiento'

_Para cambiar: 'usa [otra_bd]'_

Usuario: muestrame las tablas

Respuesta:
✅ **Encontré 4 registro(s)**

**Base de datos:** trombofilia
**SQL usado:**
```sql
SELECT schemaname AS table_schema, tablename AS table_name FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') AND schemaname NOT LIKE 'pg_%' AND schemaname NOT LIKE '_timescaledb%' ORDER BY schemaname, tablename;
```

```
table_schema | table_name
-------------+-----------
public | pacientes
public | pacientes_ok
public | tratamiento
public | variables
```

Usuario: muestrame las columnas de pacientes_ok

Respuesta:
✅ **Encontré 87 registro(s)**

**Base de datos:** trombofilia
**SQL usado:**
```sql
SELECT column_name FROM information_schema.columns WHERE table_name='pacientes_ok' ORDER BY ordinal_position;
```

```
column_name
-----------
sexo
raza
ant_inf
ant_isq
ant_clau
fum_act
diabetes
hip_art
insf_car
fibr_aur
trat_est
e_con_pp
e_con_cu
e_con_ec
e_con_lu
e_con_af
e_con_be
e_con_at
e_con_va
e_con_ar
e_con_ea
e_con_pr
e_con_ro
e_con_av
e_con_sm
sin_tvp_
var171
ep_tac_r
eptacven
ep_t_reg
ep_ecoca
ep_eco_v
var52
epecoddv
tvp_eco_
tv_l_esu
tv_l_ein
tv_l_vpo
tv_l_vme
tv_l_ves
tv_l_svc
tv_l_vre
tv_l_vrn
tv_l_vca
tv_l_yug
tv_l_ova
tv_l_sup
tv_l_pul
tv_l_ove
fr_cance
```

Usuario: dame 10 registros de pacientes_ok

Respuesta:
✅ **Encontré 10 registro(s)**

**Base de datos:** trombofilia
**SQL usado:**
```sql
SELECT * FROM "pacientes_ok" LIMIT 10;
```

```
sexo | raza | ant_inf | ant_isq | ant_clau | fum_act | diabetes | hip_art | insf_car | fibr_aur | trat_est | e_con_pp | e_con_cu | e_con_ec | e_con_lu | e_con_af | e_con_be | e_con_at | e_con_va | e_con_ar | e_con_ea | e_con_pr | e_con_ro | e_con_av | e_con_sm | sin_tvp_ | var171 | ep_tac_r | eptacven | ep_t_reg | ep_ecoca | ep_eco_v | var52 | epecoddv | tvp_eco_ | tv_l_esu | tv_l_ein | tv_l_vpo | tv_l_vme | tv_l_ves | tv_l_svc | tv_l_vre | tv_l_vrn | tv_l_vca | tv_l_yug | tv_l_ova | tv_l_sup | tv_l_pul | tv_l_ove | fr_cance | fr_cirug | fr_inmov | fr_tvp_a | fr_antfa | fr_tvs_a | fr_viaje | fr_estro | fr_embar | fr_varic | fr_antec | ana_trop | ana_dura | evn_defu | evn_reci | evn_rec2 | evn_rec3 | evn_rec4 | evn_hemo | evn_hem2 | evn_hem3 | evn_hem4 | eisq_art | eisq_inf | eisq_ang | eisq_cer | eisq_ei | eisq_ol | edadC | pesoC | tensionC | fr_can_eC | ana_hemoC | ana_plaqC | ana_neuC | ana_leucC | ana_dimeC | ana_creaC
-----+------+---------+---------+----------+---------+----------+---------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+--------+----------+----------+----------+----------+----------+-------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+---------+---------+-------+-------+----------+-----------+-----------+-----------+----------+-----------+-----------+----------
Mujer | Caucásica | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | TVP | No | No | No | No | No | No | No | No | Trombosis | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Sí | No | No | No | No | No | No | No | No | Buscada negativo | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Senior | Normal | Normal | No | Normal | Normal | Normal | Normal | Positivo | Normal
Hombre | Caucásica | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | TVP | No | No | No | No | No | No | No | No | Trombosis | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | Sí | No | Sí | Sí | No | No | No | No | No | Sí | No | No | Buscada negativo | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Senior | Normal | Normal | Sin metástasis | Bajo | Bajo | Normal | Alto | Positivo | Normal
Mujer | Caucásica | No | No | No | No | No | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | TVP | No | No | No | No | No | No | No | No | Trombosis | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Sí | No | No | No | No | No | No | No | No | No | Buscada negativo | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Senior | Normal | Normal | No | Normal | Normal | Normal | Alto | No practicado | Normal
Hombre | Caucásica | No | No | No | No | No | No | No | No | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | TVP/EP | No | No | No | No | No | No | No | No | Trombosis | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Buscada negativo | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | Senior | Normal | Normal | No | Bajo | Normal | Normal | Normal | Positivo | Elevada
Hombre | Caucásica | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | EP | No | Normal | No | No | No | No | No | No | Normal | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Sí | No | No | No | No | No | Sí | No | No | Buscada negativo | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Medio | Normal | Normal | No | Normal | Bajo | Normal | Normal | Negativo | Normal
Mujer | Caucásica | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | TVP | No | No | No | No | No | No | No | No | Trombosis | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Sí | Sí | No | No | No | No | No | No | No | No | Buscada positivo | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Medio | Normal | Normal | No | Normal | Normal | Normal | Normal | Positivo | Normal
Hombre | Caucásica | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | TVP | No | No | No | No | No | No | No | No | Normal | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Buscada negativo | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Joven | Normal | Normal | No | Normal | Normal | Normal | Normal | No practicado | Normal
Mujer | Caucásica | No | No | No | No | No | No | No | No | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | EP | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Buscada negativo | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Joven | Normal | Normal | No | Normal | Normal | Normal | Normal | No practicado | Normal
Hombre | Caucásica | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | EP | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Buscada negativo | No | Sí | No | No | No | Sí | Sí | No | No | No | No | No | No | No | No | Medio | Normal | Normal | No | Normal | Normal | Normal | Normal | Positivo | Elevada
Mujer | Caucásica | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | TVP | No | No | No | No | No | No | No | No | Normal | No | Sí | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Sí | No | Buscada positivo | No | No | No | No | No | No | No | No | No | No | No | No | No | No | No | Joven | Alto | Normal | No | Normal | Normal | Normal | Alto | No practicado | Normal
```
