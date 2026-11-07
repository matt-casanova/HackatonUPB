package com.alertspot.data.repository

import com.alertspot.data.model.ActionRequest
import com.alertspot.data.model.AlertDto
import com.alertspot.data.model.FireOverview
import com.alertspot.data.model.FirePoint
import com.alertspot.data.remote.ApiClient
import kotlinx.coroutines.delay

object FireRepositoryConfig {
    var useMockData = false
}

class FireRepository {
    
    suspend fun getHealth(): Result<Boolean> {
        if (FireRepositoryConfig.useMockData) {
            delay(200)
            return Result.success(true)
        }
        return try {
            val response = ApiClient.getApi().getHealth()
            Result.success(response.isNotEmpty())
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getOverview(): Result<FireOverview> {
        if (FireRepositoryConfig.useMockData) {
            delay(500)
            return Result.success(
                FireOverview(
                    region = "Chiquitania",
                    riskScore = 85,
                    riskLevel = "CRITICAL",
                    temperatureC = 42.0,
                    humidityPct = 18.0,
                    windKmh = 32.0,
                    smokeIndex = 0.85,
                    activeHotspots = 2,
                    sourceMode = "DEMO",
                    updatedAt = "2026-11-06T18:00:00Z"
                )
            )
        }
        return try {
            val response = ApiClient.getApi().getOverview()
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    suspend fun getPoints(): Result<List<FirePoint>> {
        if (FireRepositoryConfig.useMockData) {
            delay(500)
            return Result.success(
                listOf(
                    FirePoint("CHI-01", "IOT_NODE", -16.39, -61.05, 85, "CRITICAL", "DEMO"),
                    FirePoint("HOT-DEMO-01", "SATELLITE_HOTSPOT", -16.42, -61.08, null, null, "DEMO")
                )
            )
        }
        return try {
            val response = ApiClient.getApi().getPoints()
            Result.success(response.points)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    suspend fun getAlerts(): Result<List<AlertDto>> {
        if (FireRepositoryConfig.useMockData) {
            delay(500)
            return Result.success(
                listOf(
                    AlertDto(15, "CHI-01", 85, "PENDING", "2026-11-06T18:00:00Z", null, null, "DEMO")
                )
            )
        }
        return try {
            val response = ApiClient.getApi().getAlerts()
            Result.success(response.alerts)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    suspend fun confirmAlert(id: Int): Result<Unit> {
        if (FireRepositoryConfig.useMockData) {
            delay(500)
            return Result.success(Unit)
        }
        return try {
            ApiClient.getApi().confirmAlert(id, ActionRequest("ANDROID_DEMO"))
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    suspend fun falseAlarm(id: Int): Result<Unit> {
        if (FireRepositoryConfig.useMockData) {
            delay(500)
            return Result.success(Unit)
        }
        return try {
            ApiClient.getApi().falseAlarm(id, ActionRequest("ANDROID_DEMO"))
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}