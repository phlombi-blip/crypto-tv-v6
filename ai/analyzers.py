    # ---------------------------------------------------------
    # KI-ANALYSE PANEL
    # ---------------------------------------------------------
    st.markdown("")

    st.markdown('<div class="tv-card">', unsafe_allow_html=True)
    st.markdown('<div class="tv-title">🤖 KI-Analyse</div>', unsafe_allow_html=True)

    if not df.empty:
        # --- 1) Automatische Indikatoranalyse ---
        trend = detect_trend(df)
        rsi_div = detect_rsi_divergence(df)
        vol = detect_volatility(df)

        # --- 2) GPT-Marktkommentar ---
        ai_comment = market_commentary(
            df=df,
            symbol=st.session_state.selected_symbol,
            timeframe=st.session_state.selected_timeframe,
            trend=trend,
            rsi_divergence=rsi_div,
            volatility=vol,
        )

        st.markdown(
            f"""
            <div class="ai-box">
                <b>📊 Automatische Marktanalyse</b><br><br>
                {ai_comment}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Manuelles Aktualisieren
        if st.button("🔍 KI-Analyse aktualisieren"):
            st.rerun()

    else:
        st.info("Keine Daten für KI-Analyse.")
    st.markdown("</div>", unsafe_allow_html=True)



    # ---------------------------------------------------------
    # KI-COPILOT CHAT
    # ---------------------------------------------------------
    st.markdown("")
    st.markdown('<div class="tv-card">', unsafe_allow_html=True)
    st.markdown('<div class="tv-title">🧠 KI-CoPilot Chat</div>', unsafe_allow_html=True)

    st.markdown("""
        Stelle Fragen wie:<br>
        • „Ist das ein möglicher Breakout?“<br>
        • „Bewerte den Trend.“<br>
        • „Ist jetzt ein guter Zeitpunkt zum Einstieg?“<br>
        • „Was sagt das Volumen?“<br>
    """, unsafe_allow_html=True)

    # Chatverlauf anzeigen
    for msg in st.session_state.ai_chat_history:
        who, text = msg["role"], msg["content"]
        bubble_color = "#1e293b" if theme == "Dark" else "#e2e8f0"
        align = "left" if who == "assistant" else "right"

        st.markdown(
            f"""
            <div style='text-align:{align}; margin:6px 0;'>
                <div style='display:inline-block; padding:8px 12px; 
                            background:{bubble_color}; border-radius:8px; 
                            max-width:80%;'
                >
                    {text}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Eingabefeld
    user_msg = st.text_input("Deine Frage an den CoPilot:")
    if st.button("Senden"):
        if user_msg.strip():
            st.session_state.ai_chat_history.append(
                {"role": "user", "content": user_msg}
            )

            # Antwort vom CoPilot
            answer = ask_copilot(user_msg, df)
            st.session_state.ai_chat_history.append(
                {"role": "assistant", "content": answer}
            )

            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)



# ---------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------
if __name__ == "__main__":
    main()
