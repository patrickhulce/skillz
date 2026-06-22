use napi::bindgen_prelude::*;
use napi_derive::napi;

#[napi]
pub fn echo(input: Buffer) -> Result<Buffer> {
    let bytes = myplaceholder_rust_crate::echo(input.as_ref());
    Ok(Buffer::from(bytes))
}
