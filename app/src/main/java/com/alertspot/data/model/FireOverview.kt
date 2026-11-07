package com.alertspot.data.model

import com.google.gson.annotations.SerializedName

data class FireOverview(
    @SerializedName("region") val region: String,
    @SerializedName("risk_score") val riskScore: Int,
    @SerializedName("risk_level") val riskLevel: String,
    @SerializedName("temperature_c") val temperatureC: Double,
    @SerializedName("humidity_pct") val humidityPct: Double,
    @SerializedName("wind_kmh") val windKmh: Double,
    @SerializedName("smoke_index") val smokeIndex: Double,
    @SerializedName("active_hotspots") val activeHotspots: Int,
    @SerializedName("source_mode") val sourceMode: String,
    @SerializedName("updated_at") val updatedAt: String
)