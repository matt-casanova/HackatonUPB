package com.alertspot.data.remote

import com.alertspot.data.model.ActionRequest
import com.alertspot.data.model.AlertDto
import com.alertspot.data.model.FireOverview
import com.alertspot.data.model.FirePointsResponse
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface SatApi {
    @GET("/health")
    suspend fun getHealth(): Map<String, String>

    @GET("/api/v1/fires/overview")
    suspend fun getOverview(): FireOverview

    @GET("/api/v1/fires/points")
    suspend fun getPoints(): FirePointsResponse

    @GET("/api/v1/fires/history")
    suspend fun getHistory(@Query("node_id") nodeId: String): List<Any> // Adjust type if needed

    @GET("/api/v1/alerts")
    suspend fun getAlerts(): List<AlertDto>

    @POST("/api/v1/alerts/{id}/confirm")
    suspend fun confirmAlert(@Path("id") id: Int, @Body request: ActionRequest)

    @POST("/api/v1/alerts/{id}/false-alarm")
    suspend fun falseAlarm(@Path("id") id: Int, @Body request: ActionRequest)
}