from src.native_filter import Action, NativeFilter, NativeFilterDialog, decode_filter, encode_filter


def test_public_api_encodes_an_independent_filter():
    document = decode_filter(encode_filter(NativeFilter()))
    assert document.rules[0].action == Action.SHOW
    assert NativeFilterDialog.__name__ == "NativeFilterDialog"
