from datetime import date, time
import decimal
from typing import *

type AppointmentModel = AppointmentModel

class AppointmentModel:
    def __init__(self):
        self.appointmentDate : date = None
        self.appointmentTime : time = None
        self.clientName = None
        self.petName = None
        self.reason = None
        self.notes = None
        self.doctor = None
        self.type = None
        self.cssPath = None
        
        # Clinical Exam Page
        self.weight : float = None
        self.heartRate : int = None
        self.bodyConditionScore : int = None
        self.masterProblems : list[(date, time, str)] = []
        self.historyText = None
        self.physicalExamText = None
        self.assessmentText = None
        self.planText = None
        
        # Diagnostic And Treatment Page
        self.medications : list[MedicationModel] = []
        self.theraputicProcedures : list[TheraputicProcedureModel] = []
        self.diagnosticResults : list[DiagnosticResultModel] = []
        
        # Vaccinations Page
        self.vaccinations = []
        
        # In Clinic Notes Page
        self.clinicNotes = None
        
        
        
        self.Attachments = []

    def HasBasicInfo(self):
        return (
            self.appointmentDate is not None and 
            self.appointmentTime is not None and 
            self.clientName is not None and 
            self.petName is not None and
            self.doctor is not None and
            self.type is not None and
            self.cssPath is not None
        )
        
    def IsFullyFilled(self):
        return (
            self.HasBasicInfo()
        )
        
    def __eq__(self, other) -> bool:
        if type(other) is not type(self):
            return False
        return (
            self.appointmentDate == other.appointmentDate and
            self.appointmentTime == other.appointmentTime and
            self.clientName == other.clientName and
            self.petName == other.petName
        )
        
        
        
class MedicationModel:
    def __init__(self):
        self.date : date = None
        self.time : time = None
        self.name = None
        self.current : bool = None
        self.instructions = None
        self.prescriber = None
        self.quantity : int = None
        self.daysSupply : int = None
        self.lastDispensed : date = None
                
class TheraputicProcedureModel:
    def __init__(self):
        self.date : date = None
        self.time : time = None
        self.name = None
        self.specifics = None
        
class DiagnosticResultModel:
    def __init__(self):
        self.date : date = None
        self.time : time = None
        self.vetName = None
        self.labReference = None
        self.outcomeText = None
        self.specifics = None
        self.results : list[DiagnosticResultSpecificsModel] = []

class DiagnosticResultSpecificsModel:
    def __init__(self, dateValue, name, value, unit, low, high, qualifier):
        self.date : date = dateValue
        self.name = name
        self.value : decimal = value
        self.unit = unit
        self.low : decimal = low
        self.high : decimal = high
        self.qualifier = qualifier