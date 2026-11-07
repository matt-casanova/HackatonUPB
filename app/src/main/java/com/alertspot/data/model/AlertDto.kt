package com.alertspot.data.model

import com.google.gson.annotations.SerializedName

data class AlertDto(
    @SerializedName("id") val id: Int,
    @SerializedName("node_id") val nodeId: String,
    @SerializedName("risk_score") val riskScore: Int,
    @SerializedName("status") val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("decided_at") val decidedAt: String?,
    @SerializedName("confirmed_by") val confirmedBy: String?,
    @SerializedName("source_mode") val sourceMode: String
)

data class ActionRequest(
    @SerializedName("operator") val operator: String
)