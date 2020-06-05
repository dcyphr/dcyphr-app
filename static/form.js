$(document).ready(function() {

	$('form').on('submit', function() {

		$.ajax({
			data : {

				email : $('#emailInput').val()
			},
			type : 'POST',
			url : '/reset'
		})
		.done(function(data) {

			if (data.error) {
				$('#errorAlert').text(data.error).show();
				$('#successAlert').hide();
			}
			else {
				$('#successAlert').text(data.email).show();
				$('#errorAlert').hide();
			}

		});

		event.preventDefault();

	});

});