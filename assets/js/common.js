$(document).ready(function() {
    // Hide all abstract/bibtex blocks on load
    $(".abstract.hidden, .bibtex.hidden").hide();

    function slideToggleAbstract($container) {
        var $abstract = $container.find(".abstract.hidden");
        var $bibtex   = $container.find(".bibtex.hidden");
        if ($abstract.is(':visible')) {
            $abstract.slideUp(300).removeClass('open');
        } else {
            $bibtex.slideUp(300).removeClass('open');
            $abstract.slideDown(300).addClass('open');
        }
    }

    function slideToggleBibtex($container) {
        var $abstract = $container.find(".abstract.hidden");
        var $bibtex   = $container.find(".bibtex.hidden");
        if ($bibtex.is(':visible')) {
            $bibtex.slideUp(300).removeClass('open');
        } else {
            $abstract.slideUp(300).removeClass('open');
            $bibtex.slideDown(300).addClass('open');
        }
    }

$('.abstract-toggle-block').click(function(e) {
        if ($(e.target).closest('a').length) return;
        slideToggleAbstract($(this).closest('.col-sm-8'));
    });
    $('a.bibtex').click(function() {
        slideToggleBibtex($(this).parent().parent());
    });
    $('a').removeClass('waves-effect waves-light');

    $('.pub-icon[title]').tooltip({
        delay: { show: 100, hide: 50 },
        placement: 'top',
        container: 'body',
        trigger: 'hover'
    });
});
