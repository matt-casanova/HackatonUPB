package com.alertspot.ui.fires

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.alertspot.data.model.FireOverview
import com.alertspot.data.repository.FireRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.Job
import kotlinx.coroutines.isActive

sealed class FireUiState {
    data object Loading : FireUiState()
    data class Success(val overview: FireOverview) : FireUiState()
    data class Error(val message: String) : FireUiState()
}

class FireViewModel : ViewModel() {
    private val repository = FireRepository()

    private val _uiState = MutableStateFlow<FireUiState>(FireUiState.Loading)
    val uiState: StateFlow<FireUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null

    init {
        startPolling()
    }

    fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                fetchOverview()
                delay(15000)
            }
        }
    }

    fun stopPolling() {
        pollingJob?.cancel()
    }

    fun fetchOverview() {
        viewModelScope.launch {
            _uiState.value = FireUiState.Loading
            repository.getOverview().fold(
                onSuccess = { _uiState.value = FireUiState.Success(it) },
                onFailure = { _uiState.value = FireUiState.Error(it.message ?: "Unknown error") }
            )
        }
    }
}