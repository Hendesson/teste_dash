import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objs as go
import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import os
from datetime import datetime

''''

Usa pandas para manipulação de dados, numpy para cálculos numéricos, plotly para gráficos interativos, dash e seus componentes
para criar o dashboard web, dash_bootstrap_components para estilização com Bootstrap e dash_leaflet para mapas interativos.

'''

#  Carregamento e Pré-processamento dos Dados
excel_path = "banco_dados_climaticos_consolidado (2).xlsx"


def load_data():
    df = pd.read_excel(excel_path)
    df["index"] = pd.to_datetime(df["index"])
    df["isHW"] = df["isHW"].apply(lambda x: str(x).upper())
    return df

''''
Lê um arquivo Excel com dados climáticos.
Converte a coluna index para formato de data (datetime) e normaliza a coluna isHW
para letras maiúsculas.

'''

def calculate_hw_summary(df):
    df_hw = df[df["isHW"] == "TRUE"].copy()
    df_hw_grouped = df_hw.groupby(["cidade", "year"]).size().reset_index(name="dias_hw")
    return df_hw_grouped
'''
Filtra os dias com ondas de calor (isHW == TRUE) e agrupa por cidade e ano, contando o número de dias (dias_hw).

'''

def calculate_anomalies(df, cidade):
    baseline = df[df["cidade"] == cidade]["tempMed"].mean()
    df_anomalia = df[df["cidade"] == cidade].groupby("year")["tempMed"].mean().reset_index()
    df_anomalia["anomalia"] = df_anomalia["tempMed"] - baseline
    return df_anomalia
'''
Calcula a média histórica da temperatura média (tempMed) para uma cidade (baseline) e subtrai essa baseline das temperaturas 
médias anuais para obter anomalias.

'''
# função para calcular frequência de ondas de calor por mês
def calculate_hw_monthly(df, cidade, ano):
    dff = df[(df["cidade"] == cidade) & (df["year"] == ano) & (df["isHW"] == "TRUE")].copy()
    dff["mes"] = dff["index"].dt.strftime("%B")  # Nome completo do mês
    monthly_counts = dff.groupby("mes").size().reset_index(name="frequencia")

    # ListaR de todos os meses para garantir que todos apareçam, mesmo com frequência 0
    all_months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    monthly_counts = pd.DataFrame({"mes": all_months}).merge(
        monthly_counts, on="mes", how="left"
    ).fillna({"frequencia": 0})

    return monthly_counts

''''
Filtra dados por cidade, ano e isHW == TRUE, extrai o nome do mês e conta a frequência de ondas de calor por mês. 
Garante que todos os meses apareçam, mesmo com frequência zero.

'''

#  Inicialização ( Carrega os dados, calcula o resumo de ondas de calor e extrai listas de cidades e anos
#  únicos para uso nos controles do dashboard.)
df = load_data()
df_hw_summary = calculate_hw_summary(df)
cidades = sorted(df["cidade"].unique())
anos = sorted(df["year"].unique())

#  Inicialização do App (Cria uma aplicação Dash com o tema Bootstrap para estilização.)
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Dashboard de Ondas de Calor"

#  Layout (Define um layout com um título e cinco abas dentro de um contêiner (dbc.Container).)
app.layout = dbc.Container([
    html.H2("Dashboard de Ondas de Calor", className="text-center my-4"),
# Exibe um mapa interativo com marcadores para cada cidade, usando latitude (Lat) e longitude (Long).
    # Cada marcador tem  o nome da cidade.
    dcc.Tabs([
        dcc.Tab(label="Mapa das Estações", children=[
            dl.Map([
                dl.TileLayer(),
                dl.LayerGroup([
                    dl.Marker(position=(row["Lat"], row["Long"]),
                              children=dl.Tooltip(row["cidade"]))
                    for _, row in df.drop_duplicates("cidade")[["cidade", "Lat", "Long"]].iterrows()
                ])
            ], style={"width": "100%", "height": "600px"},
                center=(df["Lat"].mean(), df["Long"].mean()), zoom=6)
        ]),
#Interface com um dropdown para selecionar a cidade, um slider para o ano e um gráfico que será atualizado dinamicamente.


        dcc.Tab(label="Temperaturas Diárias", children=[
            html.Div([
                html.Label("Cidade:"),
                dcc.Dropdown(cidades, cidades[0], id="cidade-temp"),
                html.Label("Ano:"),
                dcc.Slider(min=min(anos), max=max(anos), step=1, value=max(anos),
                           marks={int(a): str(a) for a in anos}, id="ano-temp"),
                dcc.Loading(dcc.Graph(id="grafico-temp"))
            ], className="p-4")
        ]),

        dcc.Tab(label="Anomalias Anuais", children=[
            html.Div([
                html.Label("Cidade:"),
                dcc.Dropdown(cidades, cidades[0], id="cidade-anomalia"),
                dcc.Loading(dcc.Graph(id="grafico-anomalia"))
            ], className="p-4")
        ]),
#Dropdown para selecionar a cidade e exibir um gráfico de anomalias de temperatura.


        dcc.Tab(label="Heatmap de Dias de Onda de Calor", children=[
            html.Div([
                dcc.Loading(dcc.Graph(id="heatmap-hw",
                                      figure=px.density_heatmap(df_hw_summary,
                                                                x="year", y="cidade", z="dias_hw",
                                                                color_continuous_scale="OrRd",
                                                                labels={"dias_hw": "Dias de Onda de Calor"})))
            ], className="p-4")
        ]),
# Exibe um heatmap fixo mostrando o número de dias de onda de calor por cidade e ano.

        #  aba para o gráfico polar
        dcc.Tab(label="Ondas de Calor por Mês (Polar)", children=[
            html.Div([
                html.Label("Cidade:"),
                dcc.Dropdown(cidades, cidades[0], id="cidade-polar"),
                html.Label("Ano:"),
                dcc.Dropdown(anos, max(anos), id="ano-polar"),
                dcc.Loading(dcc.Graph(id="grafico-polar"))
            ], className="p-4")
        ])
    ])
], fluid=True)


#  Callbacks Atualiza o gráfico de temperaturas diárias (máxima, média e mínima) com base na cidade e ano selecionados.
@app.callback(
    Output("grafico-temp", "figure"),
    Input("cidade-temp", "value"),
    Input("ano-temp", "value")
)
def update_temp_plot(cidade, ano):
    dff = df[(df["cidade"] == cidade) & (df["year"] == ano)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dff["index"], y=dff["tempMax"], mode="lines", name="Máxima", line=dict(color="red")))
    fig.add_trace(go.Scatter(x=dff["index"], y=dff["tempMed"], mode="lines", name="Média", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=dff["index"], y=dff["tempMin"], mode="lines", name="Mínima", line=dict(color="green")))
    fig.update_layout(title=f"Temperaturas em {cidade} ({ano})", xaxis_title="Data", yaxis_title="Temperatura (°C)")
    return fig
#Gera um gráfico de dispersão mostrando anomalias de temperatura anual para a cidade selecionada.



@app.callback(
    Output("grafico-anomalia", "figure"),
    Input("cidade-anomalia", "value")
)
def update_anomaly_plot(cidade):
    df_anomalia = calculate_anomalies(df, cidade)
    fig = px.scatter(df_anomalia, x="year", y="anomalia", size=np.abs(df_anomalia["anomalia"]),
                     title=f"Anomalias de Temperatura Média - {cidade}",
                     labels={"anomalia": "Anomalia (°C)"})
    return fig


#  callback para o gráfico polar
@app.callback(
    Output("grafico-polar", "figure"),
    Input("cidade-polar", "value"),
    Input("ano-polar", "value")
)
def update_polar_plot(cidade, ano):
    df_polar = calculate_hw_monthly(df, cidade, ano)

    # Criar o gráfico polar
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=df_polar["frequencia"],
        theta=df_polar["mes"],
        fill="toself",
        mode="lines+markers",
        line=dict(color="blue"),
        marker=dict(color="blue")
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True)
        ),
        title=f"Frequência de Ondas de Calor em {cidade} - {ano}",
        showlegend=False
    )

    return fig
#Cria um gráfico polar mostrando a frequência de ondas de calor por mês para a cidade e ano selecionados.



#  Execução inicia o servidor Dash
if __name__ == "__main__":
    app.run(debug=True)
