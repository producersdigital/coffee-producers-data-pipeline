# chirinos/column_mappings.py
# Maps each year's raw column names to standardized names.
# Based on the 2024 cleaning code as the naming standard.
# Columns with no 2024 equivalent keep a clean snake_case name.
# Only columns that are clearly the same concept get harmonized.

CHIRINOS_MAPPINGS = {

    2024: {
        # Identity & location
        'ID':                                   'nro_socio',
        'nombre productor':                     'nombre_productor',
        'BASE':                                 'base',
        'CASERIO':                              'caserio',
        'DISTRITO':                             'distrito',
        'PROVINCIA':                            'provincia',
        'socio dni':                            'dni',
        # Certification & status
        'Sellos':                               'sellos',
        'Certificacion':                        'certificacion',
        'estatus org':                          'categoria',
        'estatus propuesto':                    'categoria_propuesta',
        'Estado del socio':                     'estado_socio',
        'UE-2023':                              'certificacion_ue_anterior',
        # Demographics
        'socio genero':                         'genero',
        'DS.fecha nacim texto':                 'fecha_nacimiento',
        'Suma de DS.celular socio 1':           'telefono',
        # Membership
        'fecha ingreso texto':                  'fecha_ingreso',
        'fecha conversion texto':               'fecha_inicio_conversion',
        # Inspection
        'inspector':                            'nombre_inspector_interno',
        'inspector dni':                        'dni_inspector_interno',
        'Fecha Inspeccion':                     'fecha_ultimo_control_interno',
        # Land use
        'Suma de total hectareas':              'area_total_ha',
        'Cultivo Total':                        'cultivo_total',          # dropped in 2024 std but kept here for comprehensive view
        'Suma de total h cafe produccion':      'area_cafe',
        'Suma de total h cafe crecimiento':     'area_crecimiento',
        'Suma de total h inverna pasto':        'area_invernadero_pasto',
        'Suma de total h rastrojo purma':       'area_purma',
        'Suma de total h bosque primario':      'area_bosque',
        'Suma de total h bosque secundario':    'area_bosque_secundario',
        'Suma de total h otros cultivos':       'area_otros_cultivos',
        'Suma de numero parcelas':              'numero_parcelas',
        # Geolocation
        'Suma de coordenadas gps latitud':      'latitud',
        'Suma de coordenadas gps longitud':     'longitud',
        'Suma de altitud':                      'altitud',
        # Harvest (year-relative naming)
        'Estimado 2023':                        'cosecha_estimado_anterior_kg',
        'Estimado qq 2023':                     'cosecha_estimado_anterior_qq',
        'Acopio 2023':                          'cosecha_acopio_anterior_kg',
        'Estimado de cosecha 2024':             'cosecha_estimado_actual_qq',
        'Estimado Kg 2024':                     'cosecha_estimado_actual_kg',
        'Estimado en TM 2024':                  'cosecha_estimado_actual_tm',  # kept for comprehensive, dropped in std
        'Estimado promedio /Ha':                'rendimiento_estimado_qqha',
        'Compromiso Acopio 2024':               'compromiso_acopio_actual_qq',
        'Diferencia de estimado y compromiso':  'diferencia_estimado_compromiso',
        # Labor
        'Numero de trabajadodes temporales':    'numero_trabajadores_temporales',
        'N° Trabajadoras Mujeres':              'numero_trabajadores_mujeres',
        # Columns kept as-is (no rename needed, already clean enough)
        # N°, Ruta de inspección, Dia de inspeccion, nombre productor.1,
        # FECHA NC, EDAD, Rango de Edad, EE, Suma de DS.socio edad,
        # Proyectos, PRODUCTO BIOLOGICO, Unnamed: 56
        # → these stay with their raw names for the comprehensive dataset
    },

    2023: {
        # Identity & location
        'N°':                                   'nro_socio',
        'Nombre productor':                     'nombre_productor',
        'Base':                                 'base',
        'Caserio':                              'caserio',
        'Distrito':                             'distrito',
        'Provincia':                            'provincia',
        'DNI':                                  'dni',
        'Nombre productor.1':                   'nombre_productor_verificacion',  # duplicate verification col
        # Certification & status
        # Note: leading spaces stripped by _strip_column_names
        'Sellos':                               'sellos',
        'UE /PER 2022':                         'certificacion_ue_anterior',
        'NOP 2022':                             'certificacion_nop_anterior',
        'UE /PER 2023':                         'certificacion_ue_actual',
        'NOP 2023':                             'certificacion_nop_actual',
        # Demographics
        'Genero':                               'genero',
        'Fecha de nacimiento':                  'fecha_nacimiento',
        'Edad socio':                           'edad_socio',
        'Rango Edad':                           'rango_edad',
        # Membership & inspection
        'Fecha Ingreso':                        'fecha_ingreso',
        'Inicio conversión':                    'fecha_inicio_conversion',
        'Inspector Interno':                    'nombre_inspector_interno',
        'Resultado control interno':            'resultado_control_interno',
        'Fecha Inspeccion Interna':             'fecha_ultimo_control_interno',
        'Control Externo (Años)':               'control_externo',
        'Uso de Insumos no permitidos (Fecha y producto)': 'insumos_prohibidos',
        # Land use
        'Total Finca':                          'area_total_ha',
        'Cultivo Total':                        'cultivo_total',
        'Cultivo Producción':                   'area_cafe',
        'Cultivo Crecimiento':                  'area_crecimiento',
        'Inverna':                              'area_invernadero_pasto',
        'Rastrojo, Purma':                      'area_purma',
        'Reserva':                              'area_reserva',
        'Bosque Primario':                      'area_bosque',
        'Otros Cultivos':                       'area_otros_cultivos',
        'N° PARCELAS':                          'numero_parcelas',
        # Geolocation
        'Latitud':                              'latitud',
        'Longitud':                             'longitud',
        'Altitud':                              'altitud',
        'Rango altitud':                        'rango_altitud',
        # Harvest
        'Estiamdo 2022':                        'cosecha_estimado_anterior_qq',   # typo in source kept intentionally
        'Estimado kg 2022':                     'cosecha_estimado_anterior_kg',
        'Acopio 2022':                          'cosecha_acopio_anterior_kg',
        'Estimado producción 2023':             'cosecha_estimado_actual_qq',
        'Estimado producción 2023 Kg.':         'cosecha_estimado_actual_kg',
        'Compromiso acopio 2023':               'compromiso_acopio_actual_qq',
        'Rdto. (sacos/ha)':                     'rendimiento_estimado_qqha',
        'Rdto. (Kg/ha)':                        'rendimiento_kgha',
        'Rdto. (kg/ha)de compromiso de acopio': 'rendimiento_compromiso_kgha',
        # Labor
        'N° Trabajadioras Mujeres':             'numero_trabajadores_mujeres',
        # Kept raw (no rename): Programacion
    },

    2022: {
        # Identity & location
        'N°':                                   'nro_socio',
        'Nombre productor':                     'nombre_productor',
        'Base':                                 'base',
        'Caserio':                              'caserio',
        'Distrito':                             'distrito',
        'Provincia':                            'provincia',
        'DNI':                                  'dni',
        'DNI.1':                                'dni_verificacion',
        'DIRECCION':                            'direccion',
        # Certification & status
        # Note: leading spaces stripped by _strip_column_names
        'SELLOS':                               'sellos',
        'ESTADO':                               'estado_socio',
        'CONDICION':                            'condicion',
        'UE /PER 2021':                         'certificacion_ue_anterior',
        'UE /PER 2022':                         'certificacion_ue_actual',
        'NOP 2022':                             'certificacion_nop_actual',
        # Demographics
        'Genero':                               'genero',
        'Fecha Nacimiento':                     'fecha_nacimiento',
        'EDAD':                                 'edad_socio',
        'Rango de Edad':                        'rango_edad',
        'Celular':                              'telefono',
        # Membership & inspection
        'Fecha Ingreso':                        'fecha_ingreso',
        'Inicio conversión':                    'fecha_inicio_conversion',
        'Inspector Interno':                    'nombre_inspector_interno',
        'Resultado control interno':            'resultado_control_interno',
        'Fecha Inspeccion Interna':             'fecha_ultimo_control_interno',
        'Control Externo (Años)':               'control_externo',
        'Uso de Insumos no permitidos':         'insumos_prohibidos',
        # Land use
        'Total Finca':                          'area_total_ha',
        'Cultivo Total':                        'cultivo_total',
        'Cultivo Producción':                   'area_cafe',
        'Cultivo Crecimiento':                  'area_crecimiento',
        'Inverna':                              'area_invernadero_pasto',
        'Rastrojo, Purma':                      'area_purma',
        'Reserva':                              'area_reserva',
        'Bosque Primario':                      'area_bosque',
        'Otros Cultivos':                       'area_otros_cultivos',
        'Rango de hectareas':                   'rango_hectareas',
        # Geolocation — note: latitud/longitud/parcelas absent in 2022
        'Altitud':                              'altitud',
        # Harvest
        'Estiamdo 2021':                        'cosecha_estimado_anterior_qq',
        'Acopio 2021':                          'cosecha_acopio_anterior_kg',
        'Estimado producción 2022':             'cosecha_estimado_actual_qq',
        'TM':                                   'cosecha_estimado_actual_tm',
        'Compromiso acopio 2022':               'compromiso_acopio_actual_qq',
        'Acopio 2022':                          'cosecha_acopio_actual_kg',
        'Saldo 2022':                           'saldo_acopio_actual',
        '% cumplimiento 2022':                  'pct_cumplimiento_acopio',
        'QQ Autorizados':                       'qq_autorizados',
        'Rdto. (sacos/ha)':                     'rendimiento_estimado_qqha',
        'Rdto. (kg/ha)de compromiso de acopio': 'rendimiento_compromiso_kgha',
    },

    2021: {
        # Identity & location
        'Nº':                                   'nro_socio',
        'NOMBRE DEL PRODUCTOR':                 'nombre_productor',
        'BASE':                                 'base',
        'CASERIO':                              'caserio',
        'DISTRITO':                             'distrito',
        'PROVINCIA':                            'provincia',
        'DNI':                                  'dni',
        'DNI.1':                                'dni_verificacion',
        'APELLIDO':                             'apellido',
        'NOMBRE':                               'nombre_socio',
        # Certification & status
        'ENTIDAD DE CERTIFICACION':             'certificacion',
        'ESTATUS 2020':                         'categoria_anterior',
        'ESTATUS 2021':                         'categoria',
        'ESTADO':                               'estado_socio',
        'CONTROL EXTERNO':                      'control_externo',
        'RA':                                   'sello_ra',
        'UTZ':                                  'sello_utz',
        'BF':                                   'sello_bf',
        'RIESGO':                               'riesgo',
        # Demographics
        'GENERO':                               'genero',
        'FECHA DE NACIMIENTO':                  'fecha_nacimiento',
        'EDAD':                                 'edad_socio',
        'RANGO DE EDAD':                        'rango_edad',
        'Nº CELULAR':                           'telefono',
        # Membership & inspection
        'FECHA INGRESO':                        'fecha_ingreso',
        'INICIO DE CONVERSIÓN':                 'fecha_inicio_conversion',
        'NOMBRE INSPECTOR':                     'nombre_inspector_interno',
        'DNI INSPECTOR':                        'dni_inspector_interno',
        'RESULTADOS DEL CONTROL INTERNO':       'resultado_control_interno',
        'FECHA DE INSPECCION INTERNA':          'fecha_ultimo_control_interno',
        'Insumos prohibidos':                   'insumos_prohibidos',
        'DIA':                                  'dia_inspeccion',
        'MES':                                  'mes_inspeccion',
        'AÑO':                                  'año_inspeccion_raw',   # avoid clash with our new año_inspeccion col
        # Land use
        'HA TOTAL':                             'area_total_ha',
        'CAFÉ PRODUCCION':                      'area_cafe',
        'CAFÉ CRECIMIENTO':                     'area_crecimiento',
        'INVERNA/PASTO':                        'area_invernadero_pasto',
        'RASTROJO/PURMA':                       'area_purma',
        'RESERVA':                              'area_reserva',
        'BOSQUE':                               'area_bosque',
        'REFORESTACION':                        'area_reforestacion',
        'ORTOS CULTUVOS':                       'area_otros_cultivos',  # typo in source
        'MAIZ':                                 'area_maiz',
        'CACAO':                                'area_cacao',
        'CAÑA':                                 'area_cana',
        'PAN LLEVAR':                           'area_pan_llevar',
        'PIÑA':                                 'area_pina',
        'PLATANO':                              'area_platano',
        'Rango de hectareas':                   'rango_hectareas',
        'Nº PARCELAS':                          'numero_parcelas',
        # Geolocation
        'LATUTUD':                              'latitud',              # typo in source
        'LONGITUD':                             'longitud',
        'ALTITUD':                              'altitud',
        # Harvest
        'COMP ACOPIO 2020':                     'compromiso_acopio_anterior_qq',
        'ACOPIO 2020':                          'cosecha_acopio_anterior_kg',
        'ESTIMADO 2021':                        'cosecha_estimado_actual_qq',
        'COMP- ACOPIO 2021':                    'compromiso_acopio_actual_qq',
        'PRODUCTIVIDAD QQ/HA':                  'rendimiento_estimado_qqha',
        'PRODUCTIVIDAD Kg/Ha':                  'rendimiento_kgha',
    },

    2020: {
        # Identity & location
        'Nº':                                   'nro_socio',
        'NOMBRE DEL PRODUCTOR':                 'nombre_productor',
        'BASE':                                 'base',
        'CASERIO':                              'caserio',
        'DISTRITO':                             'distrito',
        'PROVINCIA':                            'provincia',
        'DNI':                                  'dni',
        # Certification & status
        'ESTATUS 2019':                         'categoria_anterior',
        'ESTATUS 2020':                         'categoria',
        'ESTADO':                               'estado_socio',
        'CONTROL EXTERNO':                      'control_externo',
        'RAINFOREST ALLIANCE':                  'sello_ra',
        'UTZ':                                  'sello_utz',
        'BIRD FRIENDLY':                        'sello_bf',
        'SELLOS':                               'sellos',
        # Demographics
        'GENERO':                               'genero',
        'FECHA NACIMIENTO':                     'fecha_nacimiento',
        'EDAD':                                 'edad_socio',
        'RANGO DE EDAD':                        'rango_edad',
        'CELULAR':                              'telefono',
        # Membership & inspection
        'FECHA INGRESO':                        'fecha_ingreso',
        'INICIO DE CONVERSIÓN':                 'fecha_inicio_conversion',
        'INSPECTOR':                            'nombre_inspector_interno',
        'DNI INSPECTOR':                        'dni_inspector_interno',
        'RESULTADOS DE CONTROL INTERNO':        'resultado_control_interno',
        'FECHA INSPECCION':                     'fecha_ultimo_control_interno',
        'INSUMOS PROHIBIDOS':                   'insumos_prohibidos',
        # Land use
        'AREA TOTAL':                           'area_total_ha',
        'CAFÉ PRODUCCION':                      'area_cafe',
        'CAFE CRECIMIENTO':                     'area_crecimiento',
        'INVERNA PASTO':                        'area_invernadero_pasto',
        'RASTROJO PURMA':                       'area_purma',
        'RESERVA':                              'area_reserva',
        'BOSQUE PRIMARIO':                      'area_bosque',
        'REFORESTACION':                        'area_reforestacion',
        'RESERVA/REFORESTACION':                'area_reserva_reforestacion',
        'OTROS CULTIVOS 1':                     'area_otros_cultivos_detalle',
        'OTROS CULTIVOS':                       'area_otros_cultivos',
        'MAIZ':                                 'area_maiz',
        'CACAO':                                'area_cacao',
        'CAÑA':                                 'area_cana',
        'PAN LLEVAR':                           'area_pan_llevar',
        'PIÑA':                                 'area_pina',
        'PLATANO':                              'area_platano',
        'Rango':                                'rango_hectareas',
        'RANGO DE HA/PRODUCTOR':                'rango_ha_productor',
        'Nº PARCELAS':                          'numero_parcelas',
        # Geolocation
        'LATITUD':                              'latitud',
        'LONGITUD':                             'longitud',
        'ALTITUD':                              'altitud',
        # Harvest
        'ESTIMADO 2019':                        'cosecha_estimado_anterior_qq',
        'ACOPIO 2019':                          'cosecha_acopio_anterior_kg',
        'ESTIMADO 2020':                        'cosecha_estimado_actual_qq',
        'COMP. ACOPIO 2020':                    'compromiso_acopio_actual_qq',
        'ACOPIO 2020':                          'cosecha_acopio_actual_kg',
        'REDTO (SACOS/HA)':                     'rendimiento_estimado_qqha',
        'TM':                                   'cosecha_estimado_actual_tm',
    },
}
















