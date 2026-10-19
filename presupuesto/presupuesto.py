import streamlit as st
import plotly.graph_objects as go
import calendar
import pandas as pd
from datetime import date, datetime
from base_datos import (crear_tabla, cargar_ejemplos, meses_disponibles,
                        ultimos_movimientos, totales, gastos_por_categoria,
                        control_quincenas, insertar_movimiento,
                        actualizar_movimiento, eliminar_movimiento,
                        guardar_presupuesto, listar_presupuesto,
                        movimientos_del_mes, historial, periodo,
                        movimientos_calendario, gastos_categoria_calendario)

# ---------- 1. CONFIGURACIÓN ----------
st.set_page_config(
    page_title="Presupuesto",
    page_icon="👛",
    layout="wide",
)

# ---------- 2. ESTILOS CSS ----------
st.markdown("""
<style>
    /* Fondo general */
    .stApp { background-color: #F8F8FA; }

    /* Sidebar rojo */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #D90009 0%, #A30007 100%);
    }
    [data-testid="stSidebar"] * { color: white !important; }

    /* Texto oscuro dentro de los inputs del sidebar */
    [data-testid="stSidebar"] input { color: #111 !important; }

    /* Tarjetas */
    .card {
        background: white;
        border-radius: 14px;
        padding: 20px;
        border: 1px solid #EEE;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .card-label { color: #666; font-size: 15px; margin: 0; }
    .card-value { font-size: 28px; font-weight: 700; margin: 4px 0 0 0; color: #111; }
    .card-delta { color: #0A9B4B; font-size: 14px; margin-top: 6px; }

    /* Botón rojo */
    div.stButton > button,
    [data-testid="stFormSubmitButton"] > button {
        background-color: #D90009;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 14px 20px;
        font-weight: 600;
        width: 100%;
    }
    div.stButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        background-color: #A30007;
        color: white;
    }

    /* Contenedores de gráficas y tablas */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: white;
        border-radius: 14px;
    }

    /* Tabla de control de gastos */
    .tabla-control { width: 100%; border-collapse: collapse; font-size: 14px; color: #111; }
    .tabla-control th {
        background: #F8F8FA; color: #444; padding: 10px 8px;
        text-align: right; font-weight: 600;
    }
    .tabla-control td { padding: 10px 8px; text-align: right; border-bottom: 1px solid #EEE; }
    .tabla-control th:first-child, .tabla-control td:first-child { text-align: left; }
    .tabla-control tr.total td { font-weight: 700; border-top: 2px solid #111; background: #FAFAFA; }
    .tabla-control .mes { background: #E8F7EC; }
    .pos { color: #0A9B4B; font-weight: 600; }
    .neg { color: #D90009; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ---------- 3. FUNCIONES Y BASE DE DATOS ----------
def formato(valor):
    """1250000 -> $ 1.250.000"""
    return f"$ {valor:,.0f}".replace(",", ".")


def formato_dif(valor):
    """Diferencia con signo: -$ 24.000 (rojo) o $ 11.500 (verde)."""
    if valor < 0:
        return f"<span class='neg'>-{formato(abs(valor))}</span>"
    return f"<span class='pos'>{formato(valor)}</span>"


NOMBRES_MES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def nombre_mes(aaaa_mm):
    """'2025-04' -> 'Abr 2025'"""
    anio, mes = aaaa_mm.split("-")
    return f"{NOMBRES_MES[int(mes) - 1]} {anio}"


crear_tabla()
cargar_ejemplos()

METODOS = ["Efectivo", "Tarjeta", "Transferencia"]


def ir_a_movimientos():
    st.session_state["pagina"] = "🔁 Movimientos"


def mostrar_movimientos(mes):
    st.markdown("### 🔁 Movimientos")

    mensaje = st.session_state.pop("mensaje", None)
    if mensaje:
        st.success(mensaje)

    cats_gasto = listar_presupuesto()["categoria"].tolist()

    # ----- A. REGISTRAR UN MOVIMIENTO NUEVO -----
    with st.container(border=True):
        st.markdown("#### ＋ Registrar movimiento")
        tipo = st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True, key="nuevo_tipo")
        opciones = cats_gasto if tipo == "Gasto" else ["Ingresos"]

        with st.form("form_nuevo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            fecha = c1.date_input("Fecha", value=date.today(), format="DD/MM/YYYY")
            monto = c2.number_input("Monto", min_value=0, value=0, step=1000)
            descripcion = c1.text_input("Descripción")
            categoria = c2.selectbox("Categoría", opciones)
            metodo = c1.selectbox("Método", METODOS)
            guardar = st.form_submit_button("Guardar movimiento")

        if guardar:
            if not descripcion.strip():
                st.error("Escribe una descripción.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que 0.")
            else:
                insertar_movimiento(fecha.isoformat(), descripcion.strip(),
                                    categoria, metodo, tipo, monto)
                st.session_state["mensaje"] = f"✅ Guardado: {descripcion.strip()} ({formato(monto)})"
                st.rerun()

    # ----- B. EDITAR O ELIMINAR -----
    st.write("")
    df = movimientos_del_mes(mes)
    with st.container(border=True):
        st.markdown(f"#### ✏️ Editar o eliminar · {nombre_mes(mes)}")
        if df.empty:
            st.info("No hay movimientos en este mes.")
        else:
            vista = df.assign(monto=df["monto"].map(formato))[
                ["fecha", "descripcion", "categoria", "metodo", "tipo", "monto"]]
            st.dataframe(vista, hide_index=True)

            etiquetas = {
                int(r["id"]): f"{r['fecha']} · {r['descripcion']} · {formato(r['monto'])}"
                for _, r in df.iterrows()
            }
            id_sel = st.selectbox("Elige el movimiento", list(etiquetas),
                                  format_func=lambda i: etiquetas[i])
            fila = df[df["id"] == id_sel].iloc[0]

            cats = list(dict.fromkeys(cats_gasto + ["Ingresos", fila["categoria"]]))
            metodos = list(dict.fromkeys(METODOS + [fila["metodo"]]))
            tipos = ["Gasto", "Ingreso"]

            with st.form(f"form_editar_{id_sel}"):
                c1, c2 = st.columns(2)
                e_fecha = c1.date_input(
                    "Fecha", format="DD/MM/YYYY", key=f"e_fecha_{id_sel}",
                    value=datetime.strptime(fila["fecha"], "%Y-%m-%d").date())
                e_monto = c2.number_input(
                    "Monto", min_value=0, step=1000, key=f"e_monto_{id_sel}",
                    value=int(fila["monto"]))
                e_desc = c1.text_input("Descripción", value=fila["descripcion"],
                                       key=f"e_desc_{id_sel}")
                e_cat = c2.selectbox("Categoría", cats, key=f"e_cat_{id_sel}",
                                     index=cats.index(fila["categoria"]))
                e_metodo = c1.selectbox("Método", metodos, key=f"e_met_{id_sel}",
                                        index=metodos.index(fila["metodo"]))
                e_tipo = c2.selectbox("Tipo", tipos, key=f"e_tipo_{id_sel}",
                                      index=tipos.index(fila["tipo"]))
                confirmar = st.checkbox("Confirmo que quiero eliminarlo",
                                        key=f"e_conf_{id_sel}")
                b1, b2 = st.columns(2)
                guardar_cambios = b1.form_submit_button("Guardar cambios")
                eliminar = b2.form_submit_button("Eliminar")

            if guardar_cambios:
                actualizar_movimiento(int(id_sel), e_fecha.isoformat(), e_desc.strip(),
                                      e_cat, e_metodo, e_tipo, e_monto)
                st.session_state["mensaje"] = "✏️ Movimiento actualizado"
                st.rerun()
            if eliminar:
                if confirmar:
                    eliminar_movimiento(int(id_sel))
                    st.session_state["mensaje"] = "🗑️ Movimiento eliminado"
                    st.rerun()
                else:
                    st.warning("Marca la casilla de confirmación para eliminar.")

    # ----- C. PRESUPUESTO POR CATEGORÍA (cambiar o crear) -----
    st.write("")
    with st.container(border=True):
        st.markdown("#### 🎯 Presupuesto por categoría")
        pres = listar_presupuesto()
        NUEVA = "➕ Nueva categoría"
        sel = st.selectbox("Categoría", pres["categoria"].tolist() + [NUEVA],
                           key="pres_sel")
        if sel == NUEVA:
            nombre = st.text_input("Nombre de la nueva categoría", key="pres_nombre")
            valor_ini = 0
        else:
            nombre = sel
            valor_ini = int(pres.loc[pres["categoria"] == sel, "valor"].iloc[0])
        valor = st.number_input("Presupuesto del mes", min_value=0, step=10000,
                                value=valor_ini, key=f"pres_valor_{sel}")
        if st.button("Guardar presupuesto"):
            if not nombre.strip():
                st.error("Escribe el nombre de la categoría.")
            else:
                guardar_presupuesto(nombre.strip(), valor)
                st.session_state["mensaje"] = f"🎯 Presupuesto guardado: {nombre.strip()}"
                st.rerun()


def mostrar_historial():
    st.markdown("### 📚 Historial")
    st.caption("Todo lo que has guardado, por mes completo (del 1 al 30 o 31). Nada se borra.")

    h = historial()
    if h.empty:
        with st.container(border=True):
            st.info("Todavía no hay movimientos guardados.")
        return

    # ----- Resumen por mes -----
    with st.container(border=True):
        st.markdown("#### Resumen por mes")
        filas = ""
        for _, f in h.iterrows():
            filas += (
                "<tr>"
                f"<td>{nombre_mes(f['mes'])}</td>"
                f"<td>{formato(f['ingreso'])}</td>"
                f"<td>{formato(f['gasto'])}</td>"
                f"<td>{formato_dif(f['saldo'])}</td>"
                "</tr>"
            )
        st.markdown(
            "<div style='overflow-x:auto;'><table class='tabla-control'>"
            "<tr><th>Mes</th><th>Ingresos</th><th>Gastos</th><th>Saldo</th></tr>"
            f"{filas}</table></div>",
            unsafe_allow_html=True,
        )

    # ----- Detalle de un mes -----
    st.write("")
    with st.container(border=True):
        mes_h = st.selectbox("Ver el detalle del mes", h["mes"].tolist(),
                             format_func=nombre_mes, key="mes_historial")
        anio, num = mes_h.split("-")
        ultimo = calendar.monthrange(int(anio), int(num))[1]
        st.markdown(f"#### Detalle de {nombre_mes(mes_h)} · del 1 al {ultimo}")

        st.markdown("**En qué gastaste**")
        cat = gastos_categoria_calendario(mes_h)
        if cat.empty:
            st.info("No hay gastos en este mes.")
        else:
            total = cat["total"].sum()
            filas = ""
            for _, f in cat.iterrows():
                filas += (
                    "<tr>"
                    f"<td>{f['categoria']}</td>"
                    f"<td>{formato(f['total'])}</td>"
                    f"<td>{f['total'] / total:.0%}</td>"
                    "</tr>"
                )
            filas += (
                "<tr class='total'>"
                f"<td>TOTAL GASTADO</td><td>{formato(total)}</td><td>100%</td>"
                "</tr>"
            )
            st.markdown(
                "<div style='overflow-x:auto;'><table class='tabla-control'>"
                "<tr><th>Categoría</th><th>Gastado</th><th>%</th></tr>"
                f"{filas}</table></div>",
                unsafe_allow_html=True,
            )

        st.write("")
        st.markdown("**Todos los movimientos**")
        d = movimientos_calendario(mes_h)
        vista = d.assign(monto=d["monto"].map(formato))[
            ["fecha", "descripcion", "categoria", "metodo", "tipo", "monto"]]
        st.dataframe(vista, hide_index=True)


# ---------- 4. SIDEBAR ----------
with st.sidebar:
    st.markdown("## 👛 Mi Presupuesto")
    st.caption("Organiza hoy, cumple mañana")
    st.write("")

    pagina = st.radio(
        "Menú",
        ["🏠 Inicio", "🔁 Movimientos", "📚 Historial", "📊 Categorías",
         "📈 Reportes", "🎯 Metas", "⚙️ Configuración"],
        label_visibility="collapsed",
        key="pagina",
    )

    st.write("")
    st.write("")
    st.markdown("**Pequeños hábitos,  \ngrandes metas**")

# ---------- 5. ENCABEZADO ----------
col_saludo, col_fecha = st.columns([4, 1])
with col_saludo:
    st.title("¡Hola, Santiago!")
    st.caption("Aquí tienes un resumen de tu presupuesto.")
    mes_hoy, q_hoy = periodo(date.today().isoformat())
    st.caption(f"📅 Hoy estás en la {q_hoy}ª quincena de {nombre_mes(mes_hoy)} "
               f"({'30 – 14' if q_hoy == 1 else '15 – 29'})")
with col_fecha:
    meses = sorted(set(meses_disponibles() + [periodo(date.today().isoformat())[0]]), reverse=True)
    mes = st.selectbox(
        "Mes",
        meses,
        format_func=nombre_mes,
        label_visibility="collapsed",
    )

# ---------- PÁGINAS APARTE ----------
if pagina == "🔁 Movimientos":
    mostrar_movimientos(mes)
    st.stop()

if pagina == "📚 Historial":
    mostrar_historial()
    st.stop()


# ---------- DATOS DESDE SQL (del mes elegido) ----------
ingresos, gastos = totales(mes)
saldo = ingresos - gastos

# ---------- 6. TARJETAS DE RESUMEN ----------
c1, c2, c3, c4 = st.columns([2, 1.3, 1.3, 1.6])

with c1:
    st.markdown(f"""
    <div class="card">
        <p class="card-label">Saldo disponible</p>
        <p class="card-value">{formato(saldo)}</p>
        <p class="card-delta">↑ +12% vs. mes anterior</p>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="card">
        <p class="card-label">Ingresos</p>
        <p class="card-value">{formato(ingresos)}</p>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="card">
        <p class="card-label">Gastos</p>
        <p class="card-value">{formato(gastos)}</p>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.button("＋ Registrar movimiento", on_click=ir_a_movimientos)

# ---------- 7. GRÁFICAS ----------
st.write("")
g1, g2 = st.columns([1.15, 1])

# ----- 7.1 DONA: Gastos por categoría -----
with g1:
    with st.container(border=True):
        st.markdown("#### Gastos por categoría")

        df_cat = gastos_por_categoria(mes)
        categorias = df_cat["categoria"].tolist()
        valores = df_cat["total"].tolist()
        porcentajes = [v / gastos for v in valores] if gastos > 0 else []
        colores = ["#D90009", "#E8333D", "#F07078", "#F9B8BC", "#FBD3D5",
                   "#B0000A", "#8A0007", "#FF8A8F", "#FFB3B7", "#C4545B"]

        col_dona, col_leyenda = st.columns([1, 1.2])

        with col_dona:
            fig_dona = go.Figure(go.Pie(
                labels=categorias,
                values=valores,
                hole=0.68,
                sort=False,
                marker=dict(colors=colores),
                textinfo="none",
            ))
            fig_dona.add_annotation(
                text=f"<b>{formato(gastos)}</b><br>Total gastos",
                showarrow=False,
                font=dict(size=14),
            )
            fig_dona.update_layout(
                showlegend=False,
                margin=dict(l=0, r=0, t=0, b=0),
                height=250,
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_dona, use_container_width=True)

        with col_leyenda:
            for nombre, valor, p, color in zip(categorias, valores, porcentajes, colores):
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between;
                            padding:6px 0; border-bottom:1px solid #EEE; font-size:14px;">
                    <span><span style="color:{color}; font-size:18px;">●</span> {nombre}</span>
                    <span>{formato(valor)} &nbsp; <span style="color:#999;">{p:.0%}</span></span>
                </div>
                """, unsafe_allow_html=True)

# ----- 7.2 BARRAS: Resumen mensual -----
with g2:
    with st.container(border=True):
        st.markdown("#### Resumen mensual")

        # Datos de ejemplo (los conectaremos a SQL más adelante)
        meses_graf = ["Ene", "Feb", "Mar", "Abr"]
        ingresos_mes = [1_500_000, 1_600_000, 1_800_000, ingresos]
        gastos_mes = [900_000, 1_000_000, 1_200_000, gastos]

        fig_barras = go.Figure()
        fig_barras.add_bar(x=meses_graf, y=ingresos_mes, name="Ingresos",
                           marker_color="#D90009")
        fig_barras.add_bar(x=meses_graf, y=gastos_mes, name="Gastos",
                           marker_color="#F9B8BC")
        fig_barras.update_layout(
            barmode="group",
            height=270,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.15, x=0.3),
            yaxis=dict(gridcolor="#EEE"),
        )
        st.plotly_chart(fig_barras, use_container_width=True)

# ---------- 8. CONTROL DE GASTOS (como tu Excel) ----------
st.write("")
with st.container(border=True):
    st.markdown(f"#### Control de gastos · {nombre_mes(mes)}")
    st.caption("1ª quincena: del 30 al 14 · 2ª quincena: del 15 al 29. "
               "Estimado = presupuesto / 2. Ejecutado = lo que registraste. "
               "Verde = te sobró, rojo = te pasaste.")

    ctrl = control_quincenas(mes)

    filas = ""
    for _, f in ctrl.iterrows():
        filas += (
            "<tr>"
            f"<td>{f['categoria']}</td>"
            f"<td>{formato(f['valor'])}</td>"
            f"<td>{formato(f['estimado_1'])}</td>"
            f"<td>{formato(f['ejecutado_1'])}</td>"
            f"<td>{formato_dif(f['dif_1'])}</td>"
            f"<td>{formato(f['estimado_2'])}</td>"
            f"<td>{formato(f['ejecutado_2'])}</td>"
            f"<td>{formato_dif(f['dif_2'])}</td>"
            f"<td class='mes'>{formato(f['total_mes'])}</td>"
            f"<td class='mes'>{formato_dif(f['dif_mes'])}</td>"
            "</tr>"
        )

    # Fila de totales
    t = ctrl.sum(numeric_only=True)
    filas += (
        "<tr class='total'>"
        "<td>TOTAL</td>"
        f"<td>{formato(t['valor'])}</td>"
        f"<td>{formato(t['estimado_1'])}</td>"
        f"<td>{formato(t['ejecutado_1'])}</td>"
        f"<td>{formato_dif(t['dif_1'])}</td>"
        f"<td>{formato(t['estimado_2'])}</td>"
        f"<td>{formato(t['ejecutado_2'])}</td>"
        f"<td>{formato_dif(t['dif_2'])}</td>"
        f"<td class='mes'>{formato(t['total_mes'])}</td>"
        f"<td class='mes'>{formato_dif(t['dif_mes'])}</td>"
        "</tr>"
    )

    st.markdown(
        "<div style='overflow-x:auto;'>"
        "<table class='tabla-control'>"
        "<tr><th>Descripción</th><th>Valor</th>"
        "<th>Estimado 1ª (30–14)</th><th>Ejecutado</th><th>Diferencia</th>"
        "<th>Estimado 2ª (15–29)</th><th>Ejecutado</th><th>Diferencia</th>"
        "<th>Total mes</th><th>Diferencia mes</th></tr>"
        f"{filas}</table></div>",
        unsafe_allow_html=True,
    )

# ---------- 9. ÚLTIMOS MOVIMIENTOS ----------
MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]


def formato_fecha(texto):
    f = pd.to_datetime(texto)
    return f"{f.day} {MESES[f.month - 1]}. {f.year}"


st.write("")
with st.container(border=True):
    st.markdown("#### Últimos movimientos")

    df = ultimos_movimientos(4)

    filas = ""
    for _, fila in df.iterrows():
        if fila["tipo"] == "Gasto":
            monto = f"-{formato(fila['monto'])}"
            color = "#D90009"
        else:
            monto = f"+{formato(fila['monto'])}"
            color = "#0A9B4B"

        filas += (
            "<tr style='border-bottom:1px solid #EEE;'>"
            f"<td style='padding:12px 8px;'>{formato_fecha(fila['fecha'])}</td>"
            f"<td>{fila['descripcion']}</td>"
            f"<td>{fila['categoria']}</td>"
            f"<td>{fila['metodo']}</td>"
            f"<td style='color:{color}; font-weight:600;'>{monto}</td>"
            "</tr>"
        )

    st.markdown(
        "<table style='width:100%; border-collapse:collapse; text-align:left;'>"
        "<tr style='background:#F8F8FA; color:#444;'>"
        "<th style='padding:10px 8px;'>Fecha</th><th>Descripción</th>"
        "<th>Categoría</th><th>Método</th><th>Monto</th></tr>"
        f"{filas}</table>",
        unsafe_allow_html=True,
    )