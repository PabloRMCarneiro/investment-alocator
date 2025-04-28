import streamlit as st
import math
import pandas as pd
import requests
from bs4 import BeautifulSoup
import ast
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

class PriceFetchError(Exception):
    pass

def load_tickers(path: str = "tickers.txt") -> list[str]:
    content = open(path, "r").read()
    return ast.literal_eval(content)

@st.cache_data(show_spinner=False)
def fetch_prices(symbols: list[str]) -> dict[str, float]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }
    prices: dict[str, float] = {}
    for symbol in symbols:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={symbol}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Erro de rede ao buscar {symbol}: {e}")
            raise PriceFetchError(f"Não foi possível obter a cotação de {symbol}.")
        soup = BeautifulSoup(resp.text, "html.parser")
        cells = soup.select("td.data.destaque.w3 > span")
        if not cells:
            logging.error(f"Layout inesperado, cotação não encontrada para {symbol}")
            raise PriceFetchError(f"Cotação de {symbol} não encontrada.")
        raw = cells[0].text.replace(".", "").replace(",", ".")
        try:
            prices[symbol] = float(raw)
            logging.info(f"{symbol}: R$ {prices[symbol]:.2f}")
        except ValueError:
            logging.error(f"Valor inválido para {symbol}: '{raw}'")
            raise PriceFetchError(f"Formato de cotação inválido para {symbol}.")
    return prices

def allocate_portfolio(symbols: list[str], max_invest: float) -> tuple[pd.DataFrame, float]:
    prices = fetch_prices(symbols)
    share_value = max_invest / len(symbols)
    base_shares = {s: math.floor(share_value / p) for s, p in prices.items()}
    invested = sum(base_shares[s] * prices[s] for s in symbols)
    leftover = round(max_invest - invested, 2)

    if leftover > 0:
        target = int(leftover * 100)
        coin_vals = {s: int(prices[s] * 100) for s in symbols}
        max_sum = target + min(coin_vals.values())
        dp: list[dict[str, int] | None] = [None] * (max_sum + 1)
        dp[0] = {s: 0 for s in symbols}

        best = None
        for amount in range(max_sum + 1):
            combo = dp[amount]
            if combo is None:
                continue
            if amount >= target:
                best = combo
                break
            for s in symbols:
                new_amt = amount + coin_vals[s]
                if new_amt <= max_sum and dp[new_amt] is None:
                    next_combo = combo.copy()
                    next_combo[s] += 1
                    dp[new_amt] = next_combo

        final_shares = {
            s: base_shares[s] + (best.get(s, 0) if best else 0)
            for s in symbols
        }
    else:
        final_shares = base_shares

    total_spent = sum(final_shares[s] * prices[s] for s in symbols)
    remainder = round(max_invest - total_spent, 2)

    data = [
        {
            "Ticker": s,
            "Quantidade": final_shares[s],
            "Cotação (R$)": prices[s],
            "Percentual (%)": round((prices[s]/round(final_shares[s] * prices[s], 2)*100), 2),
            "Total Investido (R$)": round(final_shares[s] * prices[s], 2)
        }
        for s in symbols
    ]
    return pd.DataFrame(data), remainder

def main():
    st.set_page_config(page_title="Alocador de Ações", layout="centered")
    st.title("Alocador de Investimento em Ações")
    tickers = load_tickers()

    selected = st.multiselect(
        "Selecione os tickers",
        options=tickers,
        help="Escolha um ou mais papéis para alocar"
    )
    max_value = st.number_input("Valor máximo (R$)", min_value=0.0, step=1.0)

    if st.button("Calcular alocação"):
        if not selected:
            st.warning("Por favor, selecione ao menos um ticker.")
            return
        try:
            df, remainder = allocate_portfolio(selected, max_value)
            st.dataframe(df, hide_index=True)
            if remainder < 0:
                st.markdown(f"**Acréscimo necessário:** R$ {abs(remainder):.2f}")
                st.markdown(f"**Valor total:** R$ {max_value + abs(remainder):.2f}")
            else:
                st.markdown(f"**Restante:** R$ {remainder:.2f}")
                st.markdown(f"**Valor total:** R$ {max_value - abs(remainder):.2f}")
        except PriceFetchError as e:
            st.error(str(e))
        except Exception as e:
            logging.exception("Erro inesperado")
            st.error("Ocorreu um erro inesperado. Tente novamente mais tarde.")

if __name__ == "__main__":
    main()
