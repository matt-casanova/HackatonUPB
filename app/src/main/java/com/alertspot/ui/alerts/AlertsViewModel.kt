package com.alertspot.ui.alerts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.alertspot.data.model.AlertDto
import com.alertspot.data.repository.FireRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive

sealed class AlertsUiState {
    data object Loading : AlertsUiState()
    data class Success(val alerts: List<AlertDto>) : AlertsUiState()
    data class Error(val message: String) : AlertsUiState()
}

class AlertsViewModel : ViewModel() {
    private val repository = FireRepository()

    private val _uiState = MutableStateFlow<AlertsUiState>(AlertsUiState.Loading)
    val uiState: StateFlow<AlertsUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null

    init {
        startPolling()
    }

    fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                fetchAlerts()
                delay(15000)
            }
        }
    }

    fun stopPolling() {
        pollingJob?.cancel()
    }

    fun fetchAlerts() {
        viewModelScope.launch {
            _uiState.value = AlertsUiState.Loading
            repository.getAlerts().fold(
                onSuccess = { _uiState.value = AlertsUiState.Success(it) },
                onFailure = { _uiState.value = AlertsUiState.Error(it.message ?: "Unknown error") }
            )
        }
    }

    fun confirmAlert(id: Int) {
        viewModelScope.launch {
            repository.confirmAlert(id).onSuccess {
                fetchAlerts()
            }
        }
    }

    fun falseAlarm(id: Int) {
        viewModelScope.launch {
            repository.falseAlarm(id).onSuccess {
                fetchAlerts()
            }
        }
    }
}