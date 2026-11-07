package com.alertspot.ui.fires

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.alertspot.data.model.FirePoint
import com.alertspot.data.repository.FireRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive

sealed class FireMapUiState {
    data object Loading : FireMapUiState()
    data class Success(val points: List<FirePoint>) : FireMapUiState()
    data class Error(val message: String) : FireMapUiState()
}

class FireMapViewModel : ViewModel() {
    private val repository = FireRepository()

    private val _uiState = MutableStateFlow<FireMapUiState>(FireMapUiState.Loading)
    val uiState: StateFlow<FireMapUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null

    init {
        startPolling()
    }

    fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                fetchPoints()
                delay(15000)
            }
        }
    }

    fun stopPolling() {
        pollingJob?.cancel()
    }

    fun fetchPoints() {
        viewModelScope.launch {
            _uiState.value = FireMapUiState.Loading
            repository.getPoints().fold(
                onSuccess = { _uiState.value = FireMapUiState.Success(it) },
                onFailure = { _uiState.value = FireMapUiState.Error(it.message ?: "Unknown error") }
            )
        }
    }
}