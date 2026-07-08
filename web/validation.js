const form = document.querySelector("#applicationForm");
const successMessage = document.querySelector("#formSuccess");
const resetButton = document.querySelector("#resetButton");

if (form) {
	const fieldIds = [
		"fullName",
		"idNumber",
		"email",
		"phone",
		"birthDate",
		"city",
		"preferredBranch",
		"position",
		"experienceYears",
		"salaryExpectation",
		"startDate",
		"motivation",
		"terms",
	];

	const showError = (fieldId, message) => {
		const field = document.getElementById(fieldId);
		const errorNode = document.getElementById(`${fieldId}Error`);

		if (!field || !errorNode) return false;

		errorNode.textContent = message;
		field.setAttribute("aria-invalid", "true");

		if (field.type !== "checkbox") {
			field.classList.add("border-red-700", "ring-2", "ring-red-700");
			field.classList.remove("border-amber-300");
		}

		return false;
	};

	const clearError = (fieldId) => {
		const field = document.getElementById(fieldId);
		const errorNode = document.getElementById(`${fieldId}Error`);

		if (!field || !errorNode) return true;

		errorNode.textContent = "";
		field.removeAttribute("aria-invalid");

		if (field.type !== "checkbox") {
			field.classList.remove("border-red-700", "ring-2", "ring-red-700");
			field.classList.add("border-amber-300");
		}

		return true;
	};

	const calculateAge = (birthDateValue) => {
		const birthDate = new Date(birthDateValue);
		const today = new Date();
		let age = today.getFullYear() - birthDate.getFullYear();
		const monthDifference = today.getMonth() - birthDate.getMonth();

		if (monthDifference < 0 || (monthDifference === 0 && today.getDate() < birthDate.getDate())) {
			age -= 1;
		}

		return age;
	};

	const validations = {
		fullName: () => {
			const value = document.getElementById("fullName").value.trim();
			if (!value) return showError("fullName", "El nombre completo es obligatorio.");
			if (value.length < 3) return showError("fullName", "El nombre debe tener al menos 3 caracteres.");
			if (!/^[A-Za-zÁÉÍÓÚáéíóúÑñ\s'-]+$/.test(value)) {
				return showError("fullName", "Ingresa un nombre valido (solo letras y espacios).");
			}
			return clearError("fullName");
		},

		idNumber: () => {
			const value = document.getElementById("idNumber").value.trim();
			if (!value) return showError("idNumber", "El documento es obligatorio.");
			if (!/^[A-Za-z0-9-]{6,15}$/.test(value)) {
				return showError("idNumber", "El documento debe tener entre 6 y 15 caracteres validos.");
			}
			return clearError("idNumber");
		},

		email: () => {
			const value = document.getElementById("email").value.trim();
			if (!value) return showError("email", "El correo electronico es obligatorio.");
			if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
				return showError("email", "Ingresa un correo electronico valido.");
			}
			return clearError("email");
		},

		phone: () => {
			const value = document.getElementById("phone").value.trim();
			if (!value) return showError("phone", "El telefono es obligatorio.");
			if (!/^\+?[0-9\s-]{7,20}$/.test(value)) {
				return showError("phone", "Ingresa un telefono valido (7 a 20 digitos, espacios o guiones).");
			}
			return clearError("phone");
		},

		birthDate: () => {
			const value = document.getElementById("birthDate").value;
			if (!value) return showError("birthDate", "La fecha de nacimiento es obligatoria.");

			const age = calculateAge(value);
			if (Number.isNaN(age) || age < 18) {
				return showError("birthDate", "Debes tener al menos 18 anos para aplicar.");
			}
			return clearError("birthDate");
		},

		city: () => {
			const value = document.getElementById("city").value.trim();
			if (!value) return showError("city", "La ciudad es obligatoria.");
			if (value.length < 2) return showError("city", "Ingresa una ciudad valida.");
			return clearError("city");
		},

		preferredBranch: () => {
			const value = document.getElementById("preferredBranch").value;
			if (!value) return showError("preferredBranch", "Selecciona la sede de interes.");
			return clearError("preferredBranch");
		},

		position: () => {
			const value = document.getElementById("position").value;
			if (!value) return showError("position", "Selecciona el cargo al que aplicas.");
			return clearError("position");
		},

		experienceYears: () => {
			const rawValue = document.getElementById("experienceYears").value;
			const value = Number(rawValue);
			if (rawValue === "") return showError("experienceYears", "Ingresa tus anos de experiencia.");
			if (!Number.isFinite(value) || value < 0 || value > 45) {
				return showError("experienceYears", "La experiencia debe estar entre 0 y 45 anos.");
			}
			return clearError("experienceYears");
		},

		salaryExpectation: () => {
			const rawValue = document.getElementById("salaryExpectation").value;
			const value = Number(rawValue);
			if (rawValue === "") return showError("salaryExpectation", "Ingresa tu aspiracion salarial.");
			if (!Number.isFinite(value) || value <= 0) {
				return showError("salaryExpectation", "La aspiracion salarial debe ser mayor que cero.");
			}
			return clearError("salaryExpectation");
		},

		startDate: () => {
			const value = document.getElementById("startDate").value;
			if (!value) return showError("startDate", "Selecciona una fecha de inicio.");

			const selected = new Date(value);
			const today = new Date();
			today.setHours(0, 0, 0, 0);
			if (selected < today) {
				return showError("startDate", "La fecha de inicio no puede ser anterior a hoy.");
			}
			return clearError("startDate");
		},

		motivation: () => {
			const value = document.getElementById("motivation").value.trim();
			if (!value) return showError("motivation", "Este campo es obligatorio.");
			if (value.length < 30) {
				return showError("motivation", "Describe tu motivacion con al menos 30 caracteres.");
			}
			return clearError("motivation");
		},

		terms: () => {
			const checked = document.getElementById("terms").checked;
			if (!checked) return showError("terms", "Debes aceptar el tratamiento de datos para continuar.");
			return clearError("terms");
		},
	};

	const validateWorkAvailability = () => {
		const errorNode = document.getElementById("workAvailabilityError");
		const selected = document.querySelector('input[name="workAvailability"]:checked');

		if (!selected) {
			errorNode.textContent = "Selecciona tu disponibilidad de horario.";
			return false;
		}

		errorNode.textContent = "";
		return true;
	};

	const validateField = (fieldId) => {
		const validator = validations[fieldId];
		if (!validator) return true;
		return validator();
	};

	const validateForm = () => {
		let isValid = true;

		fieldIds.forEach((fieldId) => {
			const fieldValid = validateField(fieldId);
			if (!fieldValid) isValid = false;
		});

		const availabilityValid = validateWorkAvailability();
		if (!availabilityValid) isValid = false;

		return isValid;
	};

	fieldIds.forEach((fieldId) => {
		const field = document.getElementById(fieldId);
		if (!field) return;

		field.addEventListener("input", () => {
			validateField(fieldId);
			successMessage.classList.add("hidden");
		});

		field.addEventListener("blur", () => {
			validateField(fieldId);
			successMessage.classList.add("hidden");
		});
	});

	const availabilityRadios = document.querySelectorAll('input[name="workAvailability"]');
	availabilityRadios.forEach((radio) => {
		radio.addEventListener("change", () => {
			validateWorkAvailability();
			successMessage.classList.add("hidden");
		});
	});

	form.addEventListener("submit", (event) => {
		event.preventDefault();
		successMessage.classList.add("hidden");

		const isValid = validateForm();

		if (!isValid) {
			const firstError = form.querySelector('[aria-invalid="true"]');
			if (firstError) firstError.focus();
			return;
		}

		successMessage.classList.remove("hidden");
		successMessage.scrollIntoView({ behavior: "smooth", block: "nearest" });
	});

	if (resetButton) {
		resetButton.addEventListener("click", () => {
			fieldIds.forEach((fieldId) => clearError(fieldId));
			const availabilityError = document.getElementById("workAvailabilityError");
			if (availabilityError) availabilityError.textContent = "";
			successMessage.classList.add("hidden");
		});
	}
}
