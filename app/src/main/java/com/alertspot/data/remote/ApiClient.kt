package com.alertspot.data.remote

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object ApiClient {
    // Para pruebas locales (cambiar a la IP de la máquina que corre FastAPI)
    // Para emulador: http://10.0.2.2:8000
    // Para teléfono físico en misma red: http://192.168.X.X:8000
    var BASE_URL = "http://192.168.0.13:8000"

    private var retrofit: Retrofit? = null

    fun getApi(): SatApi {
        if (retrofit == null) {
            recreateRetrofit()
        }
        return retrofit!!.create(SatApi::class.java)
    }

    fun recreateRetrofit() {
        retrofit = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
}