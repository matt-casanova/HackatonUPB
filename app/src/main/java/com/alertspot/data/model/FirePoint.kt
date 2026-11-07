package com.alertspot.data.model

import com.google.gson.annotations.SerializedName

data class FirePoint(
    @SerializedName("id") val id: String,
    @SerializedName("type") val type: String,
    @SerializedName("lat") val lat: Double,
    @SerializedName("lon") val lon: Double,
    @SerializedName("risk_score") val riskScore: Int? = null,
    @SerializedName("risk_level") val riskLevel: String? = null,
    @SerializedName("source_mode") val sourceMode: String
)

data class FirePointsResponse(
    @SerializedName("points") val points: List<FirePoint>
)