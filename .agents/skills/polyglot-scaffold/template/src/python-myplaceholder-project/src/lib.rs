use pyo3::prelude::*;

#[pyfunction]
fn echo(input: &[u8]) -> Vec<u8> {
    myplaceholder_rust_crate::echo(input)
}

#[pymodule]
fn _myplaceholder_project(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(echo, m)?)?;
    Ok(())
}
